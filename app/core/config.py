import logging  
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # --- GENERAL ---
    PROJECT_NAME: str = "Servicio de Validación RIF"
    API_V1_STR: str = "/v1"
    
    # --- SEGURIDAD (Sincronizado con .env) ---
    FASTAPI_API_KEY: str = "cambiame_en_produccion"
    
    # --- MISTRAL AI ---
    MISTRAL_API_KEY: str = ""
    
    # --- SCRAPING / CONCURRENCIA ---
    # Este valor controla cuántas peticiones simultáneas hacemos al SENIAT
    MAX_CONCURRENCY: int = 5  
    
    # --- BASE DE DATOS (Sincronizado con .env) ---
    DB_POSTGRESDB_USER: str = "Admin"
    SERVER_PASSWORD: str = "password_admin"
    DB_POSTGRESDB_DATABASE: str = "n8n_db"
    
    # Nota: DB_HOST debería ser el nombre del servicio (ej: "db")
    DB_HOST: str = "localhost" 

    # Propiedad calculada para obtener la URL completa de conexión ASÍNCRONA
    # Usamos postgresql+asyncpg:// para permitir guardado incremental sin bloquear la API
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_POSTGRESDB_USER}:"
            f"{self.SERVER_PASSWORD}@{self.DB_HOST}:5432/"
            f"{self.DB_POSTGRESDB_DATABASE}"
        )

    # Configuración para cargar el archivo .env automáticamente
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8',
        extra='ignore' 
    )

# 1. Instanciamos la configuración para que esté disponible en toda la app
settings = Settings()

# 2. CONFIGURACIÓN DE LOGGING 
# Define el formato de los mensajes en la consola de Uvicorn/Docker
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# 3. Objeto logger para usar en endpoints y servicios
logger = logging.getLogger("rif-api")