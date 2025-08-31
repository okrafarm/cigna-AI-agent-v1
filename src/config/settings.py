from pydantic import BaseSettings, Field
from typing import Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    # OpenAI Configuration
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    
    # Twilio/WhatsApp Configuration
    twilio_account_sid: str = Field(..., env="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(..., env="TWILIO_AUTH_TOKEN")
    twilio_whatsapp_number: str = Field(..., env="TWILIO_WHATSAPP_NUMBER")
    
    # Cigna Configuration
    cigna_username: str = Field(..., env="CIGNA_USERNAME")
    cigna_password: str = Field(..., env="CIGNA_PASSWORD")
    cigna_login_url: str = Field(
        default="https://my.cignaglobal.com/",
        env="CIGNA_LOGIN_URL"
    )
    
    # Application Configuration
    database_path: Path = Field(
        default=Path("data/claims.db"),
        env="DATABASE_PATH"
    )
    upload_dir: Path = Field(
        default=Path("data/uploads"),
        env="UPLOAD_DIR"
    )
    export_dir: Path = Field(
        default=Path("data/exports"),
        env="EXPORT_DIR"
    )
    
    # Processing Configuration
    max_concurrent_claims: int = Field(default=3, env="MAX_CONCURRENT_CLAIMS")
    claim_check_interval: int = Field(default=3600, env="CLAIM_CHECK_INTERVAL")  # seconds
    
    # OCR Configuration
    tesseract_path: Optional[str] = Field(default=None, env="TESSERACT_PATH")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    return Settings()


# Create data directories
def setup_directories(settings: Settings):
    for directory in [
        settings.database_path.parent,
        settings.upload_dir,
        settings.export_dir
    ]:
        directory.mkdir(parents=True, exist_ok=True)