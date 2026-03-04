from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

async def validate_api_key(api_key: str = Security(api_key_header)):
    # CAMBIO AQUÍ: Ahora usamos FASTAPI_API_KEY
    if api_key == settings.FASTAPI_API_KEY:
        return api_key
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="API Key inválida o ausente"
    )