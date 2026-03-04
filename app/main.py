from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder 
from app.api.v1.endpoints import router as api_v1_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API para validación y extracción de RIFs con persistencia personalizable.",
    version="1.0.0"
)

# ---  Contratos ---
# Personalización de errores 
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    
    # jsonable_encoder convierte los objetos de error de Python a tipos 
    # serializables por JSON (como strings o dicts), evitando el error 500
    errors = jsonable_encoder(exc.errors())

    # Se toma el primer error para mostrar un mensaje limpio
    # loc[-1] nos dice el nombre del campo que falló (ej. "rif")
    error_msg = f"Error en {errors[0]['loc'][-1]}: {errors[0]['msg']}"
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "code": "VALIDATION_ERROR",
            "message": error_msg,
            "detail": errors
        }
    )

# --- RUTAS ---
app.include_router(api_v1_router, prefix="/v1")

@app.get("/health", tags=["Salud"])
async def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}

if __name__ == "__main__":
    import uvicorn
    # En local usamos el puerto 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)