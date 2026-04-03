from pydantic_settings import BaseSettings
import os
from pathlib import Path

# Base directory of the project (nexus-ugc/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Settings(BaseSettings):
    WHISPER_BINARY_PATH: str = "/usr/local/bin/whisper-main"
    WHISPER_MODEL_PATH: str = "/usr/local/share/whisper/models/ggml-base.en.bin"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_FALLBACK_MODEL: str = "qwen2.5:3b"
    OLLAMA_ANALYST_MODEL: str = ""
    OLLAMA_STYLE_MODEL: str = "qwen2.5:0.5b"
    DEV_RELOAD: bool = False
    OLLAMA_KEEP_ALIVE: str = "3m"
    ANALYSIS_BACKEND: str = "ollama"  # ollama | airllm
    ANALYSIS_AUTO_UNLOAD_AFTER_PROCESS: bool = False
    AIRLLM_MODEL_ID: str = "Qwen/Qwen2.5-3B-Instruct"
    AIRLLM_COMPRESSION: str = "4bit"
    AIRLLM_WARM_ON_START: bool = True
    OLLAMA_NUM_CTX: int = 4096
    OLLAMA_NUM_PREDICT: int = 700
    OLLAMA_STYLE_NUM_CTX: int = 1024
    OLLAMA_STYLE_NUM_PREDICT: int = 120
    ANALYSIS_TRANSCRIPT_MAX_CHARS: int = 9000
    ANALYSIS_MAX_CANDIDATES: int = 8
    WHISPER_THREADS: int = 4
    WHISPER_PROCESSORS: int = 1
    WHISPER_LANGUAGE: str = "en"
    WHISPER_TRANSLATE: bool = False
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
    CLIP_ENABLE_TRANSITIONS: bool = True
    CLIP_FADE_SECONDS: float = 0.35
    CLIP_ENABLE_SUBTLE_ZOOM: bool = True
    CLIP_ZOOM_MAX: float = 1.05
    CLIP_ENABLE_SUBTITLES: bool = True
    CLIP_SUBTITLE_PRESET: str = "bold_center"
    CLIP_SUBTITLE_MAX_WORDS: int = 10
    CLIP_ENABLE_ANIMATED_CAPTIONS: bool = True
    CLIP_CAPTION_FONT_SIZE: int = 48
    CLIP_CAPTION_HIGHLIGHT_WORDS: str = ""
    CLIP_FORMAT_PRESET: str = "vertical_9_16"
    CLIP_DURATION_DIVERSITY: float = 0.45
    ANALYSIS_ENABLE_SCENE_DETECTION: bool = False
    PROCESSING_PROFILE: str = "balanced"  # eco | balanced | quality
    VIDEO_ENCODER: str = "auto"  # auto | h264_videotoolbox | libx264
    VIDEO_THREADS: int = 2
    CAPTION_STYLE_MODE: str = "hybrid"  # rule | ai | hybrid
    CAPTION_STYLE_AI_MAX_CUES: int = 60
    CAPTION_STYLE_MIN_VARIETY: int = 3
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
