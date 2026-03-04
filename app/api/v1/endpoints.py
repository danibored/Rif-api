import uuid
import asyncio
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, status, BackgroundTasks, HTTPException
from app.schemas.rif import BatchRequest, BatchResponse, ErrorResponse
from app.core.security import validate_api_key
from app.services.rif_math import RifMathService
from app.services.seniat_service import SeniatService
from app.services.db_service import db_service
from app.core.config import logger, settings

router = APIRouter()
math_service = RifMathService()
seniat_service = SeniatService()

@router.on_event("startup")
async def startup_event():
    await db_service.init_db()

# 1. VALIDACIÓN MATEMÁTICA (Respuesta JSON Pura)
@router.post("/validar", summary="Validación matemática")
async def endpoint_validar(payload: BatchRequest, token: str = Depends(validate_api_key)):
    resultados = []
    for item in payload.items:
        res = math_service.procesar_item_completo(item.rif, item.global_id)
        
        resultados.append({
            "rif_original": res.get("RIF"),
            "global_id": res.get("CODIGO IDENTIFICADOR"),
            "es_valido": (res.get("TIPO_DE_ERROR_DESPUES") == ""),
            "rif_corregido": res.get("RIF_CORREGIDO"),
            "error_antes": res.get("TIPO_DE_ERROR_ANTES"),
            "error_despues": res.get("TIPO_DE_ERROR_DESPUES")
        })
    
    return {"total": len(resultados), "items": resultados}

# 2. EXTRACCIÓN (Retorna ID de Lote para polling en n8n)
@router.post("/extraer", response_model=BatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def endpoint_extraer(payload: BatchRequest, background_tasks: BackgroundTasks, token: str = Depends(validate_api_key)):
    id_lote = uuid.uuid4()
    await db_service.crear_lote_inicial(id_lote, payload.items, payload.retention_hours)
    background_tasks.add_task(motor_procesamiento_fondo, id_lote, payload.items)

    return {
        "id_lote": id_lote,
        "status": "PROCESANDO",
        "total_records": len(payload.items),
        "expires_on": (datetime.now() + timedelta(hours=payload.retention_hours)).isoformat(),
        "mensaje": "Lote recibido y guardado."
    }

# 3. CONSULTA DE ESTADO (Para el loop de n8n)
@router.get("/consultar/{id_lote}")
async def endpoint_consultar(id_lote: str, token: str = Depends(validate_api_key)):
    try:
        uuid_lote = uuid.UUID(id_lote)
        status_data = await db_service.obtener_estatus_lote(uuid_lote)
        if not status_data:
            raise HTTPException(status_code=404, detail="Lote no encontrado")
        return status_data
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de lote inválido")

# 4. REPORTE DE FALLIDOS (Para logs en n8n)
@router.get("/consultar/{id_lote}/fallidos")
async def endpoint_reporte_fallidos(id_lote: str, token: str = Depends(validate_api_key)):
    try:
        uuid_lote = uuid.UUID(id_lote)
        fallidos = await db_service.obtener_reporte_fallidos(uuid_lote)
        return {"id_lote": id_lote, "total_fallidos": len(fallidos), "items": fallidos}
    except ValueError:
        raise HTTPException(status_code=400, detail="ID de lote inválido")

# --- MOTOR DE FONDO ---

async def procesar_un_rif(item, id_lote: uuid.UUID, semaforo: asyncio.Semaphore):
    async with semaforo:
        try:
            resultado = await seniat_service.consultar_rif(item.rif)
            if resultado.get("error_interno"):
                await db_service.actualizar_item_rif(id_lote, item.rif, "ERROR", error_msg=resultado["error_interno"])
            else:
                await db_service.actualizar_item_rif(id_lote, item.rif, "COMPLETADO", datos=resultado)
        except Exception as e:
            await db_service.actualizar_item_rif(id_lote, item.rif, "ERROR", error_msg=str(e))

async def motor_procesamiento_fondo(id_lote: uuid.UUID, items: List):
    semaforo = asyncio.Semaphore(settings.MAX_CONCURRENCY)
    await asyncio.gather(*[procesar_un_rif(item, id_lote, semaforo) for item in items])
    await db_service.finalizar_lote(id_lote)
    logger.info(f"🏁 Lote {id_lote} finalizado.")
