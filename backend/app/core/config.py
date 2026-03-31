from pydantic_settings import BaseSettings
import os
from pathlib import Path

# Base directory of the project (nexus-ugc/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    WHISPER_BINARY_PATH: str = "/usr/local/bin/whisper-main"
    WHISPER_MODEL_PATH: str = "/usr/local/share/whisper/models/ggml-base.en.bin"
    OLLAMA_MODEL: str = "qwen2.5:32b"
    UPLOAD_DIR: str = str(BASE_DIR / "backend" / "data")
    FRONTEND_DIR: str = str(BASE_DIR / "frontend")

    class Config:
        env_file = str(BASE_DIR / ".env")

settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
