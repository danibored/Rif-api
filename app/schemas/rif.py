from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import uuid

# --- Esquema de ítem individual ---
class RifInput(BaseModel):
    """
    Representa un ítem individual de RIF dentro de un lote.
    Limpia automáticamente guiones, espacios y puntos.
    """
    rif: str = Field(
        default=..., 
        examples=["V123456789"], 
        description="RIF del contribuyente. Se permiten guiones, espacios o puntos; el sistema los limpiará automáticamente."
    )
    global_id: Optional[str] = Field(
        default=None, 
        examples=["FACTURA_001"], 
        description="ID opcional del cliente para vinculación interna."
    )

    @field_validator('rif')
    @classmethod
    def limpiar_rif(cls, v: str) -> str:
        # 1. Limpieza profunda: Quitamos caracteres especiales
        v_limpio = v.replace("-", "").replace(" ", "").replace(".", "").strip().upper()
        
        # 2. Validar alfanumérico
        if not v_limpio.isalnum():
            raise ValueError("El RIF contiene caracteres inválidos. Solo se permiten letras y números.")
            
        # 3. Validar longitud mínima
        if len(v_limpio) < 5:
            raise ValueError("El RIF es demasiado corto.")
        
        return v_limpio

# --- Esquema de lote masivo ---
class BatchRequest(BaseModel):
    """
    Contrato para la carga masiva de RIFs.
    """
    items: List[RifInput] = Field(
        ..., 
        min_length=1, 
        description="Lista de RIFs a procesar."
    )
    retention_hours: int = Field(
        24, 
        ge=1, 
        le=168, 
        description="Horas de persistencia de los datos en el sistema (1h hasta 168h/7 días)."
    )

    @field_validator('items')
    @classmethod
    def check_max_items(cls, v: List[RifInput]):
        # Validación estricta del límite de 2000 registros
        if len(v) > 2000:
            raise ValueError("El lote no puede exceder los 2000 registros.")
        return v

    @field_validator('retention_hours')
    @classmethod
    def check_max_retention(cls, v: int):
        if v > 168:
            raise ValueError("El tiempo de persistencia no puede exceder las 168 horas.")
        return v

# --- Esquemas de Respuesta ---

class BatchResponse(BaseModel):
    """
    Respuesta inmediata tras recibir un lote exitosamente.
    """
    id_lote: uuid.UUID
    status: str = "PROCESANDO"
    total_records: int
    expires_on: str = Field(..., description="Fecha estimada de expiración en formato ISO 8601.")
    mensaje: str = "Lote recibido correctamente. Use el id_lote para consultar el progreso."

class ErrorResponse(BaseModel):
    """
    Estructura estándar para respuestas de error.
    """
    code: str
    message: str
    detail: Optional[str] = None
