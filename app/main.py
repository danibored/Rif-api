from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder 
from fastapi.middleware.cors import CORSMiddleware  # <-- IMPORTAR ESTO

from app.api.v1.endpoints import router as api_v1_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="API para validación y extracción de RIFs con persistencia personalizable.",
    version="1.0.0"
)

# --- CONFIGURACIÓN DE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MANEJADOR DE ERRORES ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = jsonable_encoder(exc.errors())
    # Manejo seguro de errores de validación
    loc = errors[0]['loc'][-1] if errors[0]['loc'] else "desconocido"
    error_msg = f"Error en {loc}: {errors[0]['msg']}"
    
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
    uvicorn.run(app, host="0.0.0.0", port=8000)
