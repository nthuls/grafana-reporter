# app/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    """Application configuration."""
    # App settings
    APP_NAME: str = "Security Report Wizard"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Grafana settings
    GRAFANA_URL: str = os.getenv("GRAFANA_URL", "http://localhost:3000")
    GRAFANA_API_KEY: str = os.getenv("GRAFANA_API_KEY", "")
    GRAFANA_ORG_NAME: str = os.getenv("GRAFANA_ORG_NAME", "Main Org")
    
    # Upload settings
    UPLOAD_FOLDER: str = "app/static/uploads"
    ALLOWED_EXTENSIONS: list = ["png", "jpg", "jpeg", "svg"]
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16MB
    
    # Report settings
    DEFAULT_REPORT_TITLE: str = "Security Report"
    DEFAULT_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# Create settings instance
settings = Settings()
