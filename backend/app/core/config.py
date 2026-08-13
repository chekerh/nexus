import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory of the project (nexus-ugc/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    WHISPER_BINARY_PATH: str = "/usr/local/bin/whisper-main"
    WHISPER_MODEL_PATH: str = "/usr/local/share/whisper/models/ggml-base.en.bin"
    OLLAMA_MODEL: str = "phi3"
    OLLAMA_FALLBACK_MODEL: str = "qwen2.5:0.5b"
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
    ACCOUNT_GROUPS_DB_PATH: str = str(BASE_DIR / "backend" / "data" / "account_groups.json")
    PUBLISH_LOG_PATH: str = str(BASE_DIR / "backend" / "data" / "publish_history.json")
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    PUBLIC_BASE_URL: str = ""
    INSTAGRAM_GRAPH_VERSION: str = "v22.0"
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""
    TIKTOK_CLIENT_KEY: str = ""
    TIKTOK_CLIENT_SECRET: str = ""
    TIKTOK_API_BASE: str = "https://open.tiktokapis.com"
    TWITTER_CLIENT_ID: str = ""
    TWITTER_CLIENT_SECRET: str = ""
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
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
    LOG_FORMAT: str = "human"  # human | structured (JSON with request_id)
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "noreply@nexusugc.com"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    CAPTION_STYLE_MODE: str = "hybrid"  # rule | ai | hybrid
    CAPTION_STYLE_AI_MAX_CUES: int = 60
    CAPTION_STYLE_MIN_VARIETY: int = 3
    STRATEGIST_PROMPT_FILE: str = str(BASE_DIR / "prompts" / "strategist_system.md")
    VIRAL_SIGNALS_FILE: str = str(BASE_DIR / "prompts" / "viral_signals.md")
    CLIP_MIN_SECONDS: float = 12.0
    CLIP_MAX_SECONDS: float = 45.0
    CLIP_PADDING_SECONDS: float = 1.5

    # Caption CTA (Call-to-Action) Settings
    CAPTION_CTA_ENABLED: bool = True
    CAPTION_CTA_DEFAULT_TEXT: str = "Link in bio to try it free."
    CAPTION_CTA_END_IMAGE_PATH: str = ""  # Path to end-of-video image (optional)
    CAPTION_CTA_END_IMAGE_DURATION: float = 3.0  # Seconds to show end image
    CAPTION_CTA_END_IMAGE_CAPTION: str = ""  # Caption text burned on end image

    # JWT & Security
    JWT_SECRET: str = ""
    JWT_EXPIRY_HOURS: int = 24
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10
    RATE_LIMIT_BACKEND: str = "memory"  # memory | database
    MAX_UPLOAD_SIZE_MB: int = 500
    CSRF_ENABLED: bool = True
    SECURITY_HEADERS_ENABLED: bool = True
    CONTENT_SECURITY_POLICY: str = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self'; font-src 'self' data:; connect-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'; worker-src 'self'"
    HSTS_ENABLED: bool = True
    CSP_REPORT_URI: str = "/api/v1/csp-violation-report"
    CORS_ORIGINS: str = "http://localhost:8000,http://localhost:5173,http://127.0.0.1:8000"

    # Error Tracking
    SENTRY_DSN: str = ""

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRO_PRICE_ID: str = ""
    STRIPE_ENTERPRISE_PRICE_ID: str = ""
    DATABASE_URL: str = ""  # Empty = SQLite; set to postgresql://... for production

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    INVITE_REQUIRED_FOR_GOOGLE: bool = True

    # Whop integration
    WHOP_API_KEY: str = ""
    WHOP_WEBHOOK_SECRET: str = ""
    WHOP_PRO_PRODUCT_ID: str = ""
    WHOP_ENTERPRISE_PRODUCT_ID: str = ""

    # Dynamic Model Selection
    DYNAMIC_MODEL_SELECTION: bool = True
    SETUP_WIZARD_COMPLETE: bool = False
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    FALLBACK_API_PROVIDER: str = "openai"  # openai | openrouter | none
    FALLBACK_API_MODEL: str = "gpt-4o-mini"

    # Auto-Accounts (system-level platform credentials)
    SYSTEM_ACCOUNTS_ENABLED: bool = False
    SYSTEM_YOUTUBE_REFRESH_TOKEN: str = ""
    SYSTEM_YOUTUBE_CHANNEL_ID: str = ""
    SYSTEM_TIKTOK_ACCESS_TOKEN: str = ""
    SYSTEM_TIKTOK_REFRESH_TOKEN: str = ""
    SYSTEM_TIKTOK_OPEN_ID: str = ""
    SYSTEM_INSTAGRAM_ACCESS_TOKEN: str = ""
    SYSTEM_INSTAGRAM_USER_ID: str = ""
    SYSTEM_TWITTER_ACCESS_TOKEN: str = ""
    SYSTEM_TWITTER_USER_ID: str = ""
    SYSTEM_FACEBOOK_ACCESS_TOKEN: str = ""
    SYSTEM_FACEBOOK_PAGE_ID: str = ""
    SYSTEM_LINKEDIN_ACCESS_TOKEN: str = ""
    SYSTEM_LINKEDIN_USER_ID: str = ""

    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"))


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

# CORS zero-trust: reject wildcard in production
if settings.CORS_ORIGINS == "*" and settings.PUBLIC_BASE_URL:
    raise RuntimeError(
        "CORS_ORIGINS=* is not allowed when PUBLIC_BASE_URL is set (production). "
        "Set CORS_ORIGINS to a comma-separated list of allowed origins "
        '(e.g. "https://app.nexusugc.com,https://admin.nexusugc.com").'
    )

# Validate JWT secret
if not settings.JWT_SECRET:
    raise RuntimeError(
        'JWT_SECRET is not set. Generate one with: python3 -c "import secrets; print(secrets.token_hex(32))" '
        "and add it to your .env file: JWT_SECRET=<your-secret>"
    )
if settings.JWT_SECRET == "nexus-dev-secret-change-in-production":
    raise RuntimeError(
        "JWT_SECRET is still set to the default dev value. Generate a new one with: "
        'python3 -c "import secrets; print(secrets.token_hex(32))" '
        "and update your .env file."
    )
