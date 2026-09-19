"""
VaidyaMD HMS — Application Configuration (Production Ready)
"""

import os
import secrets
import warnings
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional, Union, List


class Settings(BaseSettings):
    # Environment & Application
    ENVIRONMENT: str = "development"  # 'development', 'staging', 'production'
    APP_NAME: str = "VaidyaMD HMS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://vaidya_md_admin:vaidya_md_secret_2026@localhost:5432/vaidya_md_db"
    
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> str:
        values = info.data
        if values.get("POSTGRES_HOST"):
            user = values.get("POSTGRES_USER")
            password = values.get("POSTGRES_PASSWORD", "")
            host = values.get("POSTGRES_HOST")
            db = values.get("POSTGRES_DB", "phr")
            
            # If using Cloud SQL Unix socket path
            if host and host.startswith("/"):
                return f"postgresql+asyncpg://{user}:{password}@/{db}?host={host}"
            return f"postgresql+asyncpg://{user}:{password}@{host}/{db}"
        return v or "postgresql+asyncpg://vaidya_md_admin:vaidya_md_secret_2026@localhost:5432/vaidya_md_db"

    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10

    # Conditional Seeding Flags
    SEED_DB: bool = False
    FORCE_DROP_DB: bool = False

    # Security & JWT
    JWT_SECRET_KEY: str = "vaidya_md_dev_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 480  # 8 hours

    # File Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50

    # CORS
    CORS_ORIGINS: Union[list[str], str] = ["http://localhost:3000", "http://localhost:8000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Production security hardening
if settings.ENVIRONMENT == "production":
    if settings.JWT_SECRET_KEY == "vaidya_md_dev_secret_key_change_in_production":
        generated_key = secrets.token_urlsafe(48)
        warnings.warn(
            "CRITICAL SECURITY WARNING: Default JWT_SECRET_KEY detected in production! "
            "Generated an ephemeral secure secret key for this session. "
            "Set JWT_SECRET_KEY in production environment variables to persist sessions across restarts.",
            RuntimeWarning,
            stacklevel=2,
        )
        settings.JWT_SECRET_KEY = generated_key
    # Enforce DEBUG=False in production
    settings.DEBUG = False
