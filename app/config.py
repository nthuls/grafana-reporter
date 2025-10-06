# app/config.py
import os
from pathlib import Path
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
    
    # OpenSearch/Elasticsearch index patterns
    OPENSEARCH_INDEX_PATTERNS: str = os.getenv("OPENSEARCH_INDEX_PATTERNS", "*")
    
    # Upload settings
    UPLOAD_FOLDER: str = "app/static/uploads"
    ALLOWED_EXTENSIONS: list = ["png", "jpg", "jpeg", "svg"]
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024  # 16MB
    
    # Report settings
    DEFAULT_REPORT_TITLE: str = "Security Report"
    DEFAULT_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    
    # Reports directory
    BASE_DIR: Path = Path(__file__).parent.parent
    REPORTS_DIR: str = str(BASE_DIR / "reports")

# Create settings instance
settings = Settings()

# Ensure directories exist
os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(settings.REPORTS_DIR, exist_ok=True)