"""
Módulo de Configuración Central
Carga las variables de entorno desde .env con Pydantic Settings o fallback nativo.
"""
import os
from pathlib import Path
from typing import Optional

# Intentar usar pydantic_settings si está disponible
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore"
        )

        TELEGRAM_BOT_TOKEN: str = ""
        TELEGRAM_ALLOWED_USER_ID: Optional[int] = None
        GEMINI_API_KEY: str = ""
        GEMINI_MODEL: str = "gemini-1.5-pro"
        GMAIL_CREDENTIALS_FILE: str = "credentials.json"
        GMAIL_TOKEN_FILE: str = "token.json"
        DATA_DIR: str = "data"
        DATABASE_PATH: str = "data/applications.db"
        GENERATED_CVS_DIR: str = "data/generated_cvs"
        BASE_CVS_DIR: str = "templates/base_cvs"
        PDF_TEMPLATES_DIR: str = "templates/pdf_styles"

        def ensure_directories(self) -> None:
            for path_str in [
                self.DATA_DIR,
                self.GENERATED_CVS_DIR,
                self.BASE_CVS_DIR,
                self.PDF_TEMPLATES_DIR,
                str(Path(self.DATABASE_PATH).parent)
            ]:
                Path(path_str).mkdir(parents=True, exist_ok=True)

    settings = Settings()

except ImportError:
    # Fallback sin dependencias instaladas aún
    def _read_env_file():
        env_dict = {}
        env_path = Path(".env")
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        env_dict[k.strip()] = v.strip()
        return env_dict

    _loaded_env = _read_env_file()

    class FallbackSettings:
        def __init__(self):
            self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", _loaded_env.get("TELEGRAM_BOT_TOKEN", ""))
            allowed_id = os.getenv("TELEGRAM_ALLOWED_USER_ID", _loaded_env.get("TELEGRAM_ALLOWED_USER_ID", ""))
            self.TELEGRAM_ALLOWED_USER_ID = int(allowed_id) if allowed_id and allowed_id.isdigit() else None
            self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", _loaded_env.get("GEMINI_API_KEY", ""))
            self.GEMINI_MODEL = os.getenv("GEMINI_MODEL", _loaded_env.get("GEMINI_MODEL", "gemini-1.5-pro"))
            self.GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", _loaded_env.get("GMAIL_CREDENTIALS_FILE", "credentials.json"))
            self.GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", _loaded_env.get("GMAIL_TOKEN_FILE", "token.json"))
            self.DATA_DIR = os.getenv("DATA_DIR", _loaded_env.get("DATA_DIR", "data"))
            self.DATABASE_PATH = os.getenv("DATABASE_PATH", _loaded_env.get("DATABASE_PATH", "data/applications.db"))
            self.GENERATED_CVS_DIR = os.getenv("GENERATED_CVS_DIR", _loaded_env.get("GENERATED_CVS_DIR", "data/generated_cvs"))
            self.BASE_CVS_DIR = os.getenv("BASE_CVS_DIR", _loaded_env.get("BASE_CVS_DIR", "templates/base_cvs"))
            self.PDF_TEMPLATES_DIR = os.getenv("PDF_TEMPLATES_DIR", _loaded_env.get("PDF_TEMPLATES_DIR", "templates/pdf_styles"))

        def ensure_directories(self) -> None:
            for path_str in [
                self.DATA_DIR,
                self.GENERATED_CVS_DIR,
                self.BASE_CVS_DIR,
                self.PDF_TEMPLATES_DIR,
                str(Path(self.DATABASE_PATH).parent)
            ]:
                Path(path_str).mkdir(parents=True, exist_ok=True)

    settings = FallbackSettings()
