# app/core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    GEMINI_API_KEY: str
    QDRANT_URL: str = "http://localhost:6333"

    model_config = {"env_file": ".env"}

settings = Settings()
