import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
FACES_DIR = UPLOAD_DIR / "faces"

os.makedirs(FACES_DIR, exist_ok=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "TimeWork - Retail Attendance System"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/timework.db")
    
    # Security / JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "timework-secret-key-change-in-production-2026-electronics-store")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 7 days
    
    # Initial Super Admin
    FIRST_SUPERUSER_USERNAME: str = os.getenv("FIRST_SUPERUSER_USERNAME", "admin")
    FIRST_SUPERUSER_PASSWORD: str = os.getenv("FIRST_SUPERUSER_PASSWORD", "admin123")
    
    # File Storage
    UPLOAD_FOLDER: Path = UPLOAD_DIR
    FACES_FOLDER: Path = FACES_DIR

    class Config:
        case_sensitive = True

settings = Settings()
