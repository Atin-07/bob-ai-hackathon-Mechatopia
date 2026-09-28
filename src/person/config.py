import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/postgres"
    )
    CORE_ALERT_URL: str = os.environ.get("CORE_ALERT_URL", "http://localhost:9000/alerts")
    MATCH_THRESHOLD: float = float(os.environ.get("MATCH_THRESHOLD", 0.4))
    ALERT_COOLDOWN_SECONDS: int = int(os.environ.get("ALERT_COOLDOWN_SECONDS", 60))
    CROP_STORAGE_DIR: str = os.environ.get("CROP_STORAGE_DIR", "./crops")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Ensure crop storage dir exists at import time
os.makedirs(settings.CROP_STORAGE_DIR, exist_ok=True)