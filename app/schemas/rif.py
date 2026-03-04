from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import uuid

# Esquema de Entrada (Request)
class RifInput(BaseModel):
    """
    Representa un ítem individual de RIF dentro de un lote.
    """
    rif: str = Field(
        ..., 
        example="V123456789", 
        description="RIF del contribuyente. Debe ser alfanumérico y sin guiones."
    )
    global_id: Optional[str] = Field(
        None, 
        example="FACTURA_001", 
        description="ID opcional del cliente para vinculación interna."
    )

    @field_validator('rif')
    @classmethod
    def validate_rif_format(cls, v: str):
        # 1. Limpieza básica
        v = v.strip().upper()
        
        # 2. Regla de Oro: No permitir guiones
        if "-" in v:
            raise ValueError("El RIF no debe contener guiones. Por favor, envíe solo letras y números.")
        
        # 3. Validar que sea puramente alfanumérico
        if not v.isalnum():
            raise ValueError("El RIF contiene caracteres inválidos. Solo se permiten letras y números.")
        
        return v

class BatchRequest(BaseModel):
    """
    Contrato para la carga masiva de RIFs.
    """
    items: List[RifInput] = Field(
        ..., 
        min_length=1, 
        max_length=2000, 
        description="Lista de RIFs a procesar (Máximo 2000 por lote)."
    )
    retention_hours: int = Field(
        24, 
        ge=1, 
        le=168, 
        description="Horas de persistencia de los datos en el sistema (1h hasta 168h/7 días). Por defecto 24h."
    )

    @field_validator('retention_hours')
    @classmethod
    def check_max_retention(cls, v: int):
        # Aunque Pydantic ya valida con ge/le, aquí podemos personalizar el mensaje si falla
        if v > 168:
            raise ValueError("El tiempo de persistencia no puede exceder las 168 horas (7 días).")
        return v

# Esquema de Salida (Response Models)

class BatchResponse(BaseModel):
    """
    Respuesta inmediata tras recibir un lote exitosamente.
    """
    id_lote: uuid.UUID
    status: str = "PROCESANDO"
    total_records: int
    expires_on: str = Field(..., description="Fecha y hora estimada de eliminación de los datos (ISO 8601).")
    mensaje: str = "Lote recibido correctamente. Use el id_lote para consultar el progreso."

class ErrorResponse(BaseModel):
    """
    Estructura estándar para respuestas de error (400, 401, 403, 500).
    """
    code: str
    message: str
    detail: Optional[str] = None