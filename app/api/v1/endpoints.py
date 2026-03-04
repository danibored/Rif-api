import uuid
import io
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, status, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

# Importación de Contratos (Schemas)
from app.schemas.rif import BatchRequest, BatchResponse, ErrorResponse
# Importación de Seguridad
from app.core.security import validate_api_key
# Importación de Servicios
from app.services.rif_math import RifMathService
from app.services.seniat_service import SeniatService
from app.services.db_service import db_service
from app.core.config import logger, settings

router = APIRouter()

# Instanciamos los servicios de lógica
math_service = RifMathService()
seniat_service = SeniatService()

# --- EVENTOS DE INICIO ---
@router.on_event("startup")
async def startup_event():
    """Al arrancar la app, nos aseguramos de que las tablas existan en Postgres."""
    await db_service.init_db()

# 1. PROCESO DE VALIDACIÓN (Síncrono - Salida: EXCEL)
@router.post(
    "/validar",
    summary="Validación matemática inmediata",
    description="Recibe un JSON de RIFs y devuelve un archivo Excel con la auditoría de Módulo 11.",
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}}
)
async def endpoint_validar(
    payload: BatchRequest,
    token: str = Depends(validate_api_key)
):
    logger.info(f"📥 Solicitud de validación matemática: {len(payload.items)} registros.")
    
    resultados = []
    for item in payload.items:
        res = math_service.procesar_item_completo(item.rif, item.global_id)
        resultados.append({
            "RIF_ORIGINAL": item.rif,
            "ID_CLIENTE": item.global_id,
            "ESTADO": "VÁLIDO" if res["valido"] else "INVÁLIDO",
            "RIF_CORREGIDO": res["rif_normalizado"],
            "DV_ESPERADO": res["dv_esperado"]
        })

    df = pd.DataFrame(resultados)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Validación_RIF')
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=auditoria_rif_{datetime.now().strftime('%Y%m%d')}.xlsx"}
    )

# 2. PROCESO DE EXTRACCIÓN (Asíncrono - Persistencia Inicial)
@router.post(
    "/extraer",
    response_model=BatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Inicia la extracción en el SENIAT"
)
async def endpoint_extraer(
    payload: BatchRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(validate_api_key)
):
    id_lote = uuid.uuid4()
    
    # Persistencia Inicial
    # Guardamos el lote y sus items en la DB antes de responderle al cliente (n8n)
    await db_service.crear_lote_inicial(
        id_lote=id_lote, 
        items=payload.items, 
        retention_hours=payload.retention_hours
    )

    # Iniciamos el motor en segundo plano
    background_tasks.add_task(motor_procesamiento_fondo, id_lote, payload.items)

    return {
        "id_lote": id_lote,
        "status": "PROCESANDO",
        "total_records": len(payload.items),
        "expires_on": (datetime.now() + timedelta(hours=payload.retention_hours)).isoformat(),
        "mensaje": "Lote recibido y guardado. Procesando en segundo plano."
    }

# 3. PROCESO DE CONSULTA (Métricas en tiempo real)
@router.get(
    "/consultar/{id_lote}",
    summary="Consulta estatus y progreso del lote"
)
async def endpoint_consultar(id_lote: str, token: str = Depends(validate_api_key)):
    # Métricas visibles desde DB
    try:
        uuid_lote = uuid.UUID(id_lote)
        status_data = await db_service.obtener_estatus_lote(uuid_lote)
        
        if not status_data:
            raise HTTPException(status_code=404, detail="Lote no encontrado")
            
        return status_data
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de lote inválido")

# 4. REPORTE DE FALLIDOS 
@router.get(
    "/consultar/{id_lote}/fallidos",
    summary="Reporte de registros con error"
)
async def endpoint_reporte_fallidos(id_lote: str, token: str = Depends(validate_api_key)):
    """Devuelve la lista de RIFs que no pudieron ser procesados."""
    try:
        uuid_lote = uuid.UUID(id_lote)
        fallidos = await db_service.obtener_reporte_fallidos(uuid_lote)
        return {
            "id_lote": id_lote,
            "total_fallidos": len(fallidos),
            "items": fallidos
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de lote inválido")



# MOTOR DE EJECUCIÓN CON CONCURRENCIA CONTROLADA
async def procesar_un_rif(item, id_lote: uuid.UUID, semaforo: asyncio.Semaphore):
    """Lógica individual de cada RIF con guardado incremental."""
    async with semaforo:  # Control de concurrencia
        try:
            logger.info(f"🔎 Consultando SENIAT: {item.rif}")
            
            # Llamada al scraper
            resultado = await seniat_service.consultar_rif(item.rif)
            
            # Guardado Incremental (Éxito o Captcha Fallido)
            if resultado.get("error_interno"):
                await db_service.actualizar_item_rif(
                    id_lote, item.rif, "ERROR", error_msg=resultado["error_interno"]
                )
            else:
                await db_service.actualizar_item_rif(
                    id_lote, item.rif, "COMPLETADO", datos=resultado
                )
                
        except Exception as e:
            logger.error(f"❌ Fallo crítico en item {item.rif}: {str(e)}")
            #  Guardado Incremental (Fallo inesperado)
            await db_service.actualizar_item_rif(
                id_lote, item.rif, "ERROR", error_msg=str(e)
            )

async def motor_procesamiento_fondo(id_lote: uuid.UUID, items: List):
    """Gestiona el lote de forma concurrente."""
    # El semáforo limita cuántos requests simultáneos hacemos
    semaforo = asyncio.Semaphore(settings.MAX_CONCURRENCY)
    
    # Creamos la lista de tareas concurrentes
    tareas = [procesar_un_rif(item, id_lote, semaforo) for item in items]
    
    # Ejecutamos todo (await masivo)
    await asyncio.gather(*tareas)
    
    # Al terminar todas, marcamos el lote como finalizado
    await db_service.finalizar_lote(id_lote)
    logger.info(f"🏁 Finalizado procesamiento del Lote: {id_lote}")