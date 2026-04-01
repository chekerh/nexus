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
    ACCOUNTS_DB_PATH: str = str(BASE_DIR / "backend" / "data" / "accounts.json")
    PUBLISH_LOG_PATH: str = str(BASE_DIR / "backend" / "data" / "publish_history.json")
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    PUBLIC_BASE_URL: str = ""
    INSTAGRAM_GRAPH_VERSION: str = "v22.0"
    TIKTOK_CLIENT_KEY: str = ""
    TIKTOK_CLIENT_SECRET: str = ""
    TIKTOK_API_BASE: str = "https://open.tiktokapis.com"
    STRATEGIST_PROMPT_FILE: str = str(BASE_DIR / "prompts" / "strategist_system.md")
    VIRAL_SIGNALS_FILE: str = str(BASE_DIR / "prompts" / "viral_signals.md")
    CLIP_MIN_SECONDS: float = 12.0
    CLIP_MAX_SECONDS: float = 45.0
    CLIP_PADDING_SECONDS: float = 1.5

    class Config:
        env_file = str(BASE_DIR / ".env")

settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
