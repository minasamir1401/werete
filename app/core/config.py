import os
import secrets
from typing import List, Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, validator

class SmartSettings(BaseSettings):
    """
    Backend Smart Intelligence Layer (Configuration)
    Automatically detects environment and scales settings.
    """
    # System Info
    PROJECT_NAME: str = "Gold Service API"
    ENV: str = "development"  # development / production / staging

    # API Configuration
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    
    # 🧠 Smart Database Discovery
    # If DATABASE_URL is provided (Cloud/Docker), it uses it.
    # Otherwise, it falls back to a smart local SQLite path.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    @validator("DATABASE_URL", pre=True)
    def assemble_db_url(cls, v: str) -> str:
        if v and v.strip():
            return v
        
        # Smart SQLite Fallback
        # Check if we are running in a container with a persistent mount point (/app/data)
        if os.path.exists("/app/data"):
            db_path = "/app/data/gold_prices.db"
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base_dir, "gold_prices.db")
            
        return f"sqlite:///{db_path}"

    # 🌍 Intelligent CORS Management
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000"
    ]

    # Auto-healing & Performance
    SQLITE_BUSY_TIMEOUT: int = 30000
    SCRAPE_INTERVAL_DEFAULT: int = 60
    
    # Discovery mode
    DEBUG: bool = True

    @validator("DEBUG", pre=True, always=True)
    def set_debug_mode(cls, v: bool, values: dict) -> bool:
        return values.get("ENV") == "development"

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

settings = SmartSettings()
