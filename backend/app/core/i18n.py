"""Backend i18n — contextvar-based translation using frontend locale JSON files."""

import json
from contextvars import ContextVar
from pathlib import Path

_current_lang = ContextVar("current_lang", default="en")

_locales: dict[str, dict[str, str]] = {}

LOCALE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "locales"

_lazy_loaded = False


def _flatten(d: dict, prefix: str = "") -> dict[str, str]:
    result = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flatten(v, key))
        else:
            result[key] = v
    return result


def load_locales():
    global _locales
    _locales.clear()
    for fname in ["en.json", "fr.json", "ar.json"]:
        path = LOCALE_DIR / fname
        if path.exists():
            with open(path) as fh:
                lang = fname.replace(".json", "")
                _locales[lang] = _flatten(json.load(fh))


def set_language(lang: str):
    _current_lang.set(lang)


def get_language() -> str:
    return _current_lang.get()


def _(key: str, default: str | None = None) -> str:
    global _lazy_loaded
    if not _lazy_loaded:
        load_locales()
        _lazy_loaded = True
    lang = _current_lang.get()
    translations = _locales.get(lang) or _locales.get("en", {})
    return translations.get(key) or default or key


class I18nMiddleware:
    """FastAPI middleware that sets language from Accept-Language header."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        accept = headers.get(b"accept-language", b"en").decode("utf-8", errors="ignore")
        if accept.startswith("fr"):
            lang = "fr"
        elif accept.startswith("ar"):
            lang = "ar"
        else:
            lang = "en"
        set_language(lang)
        await self.app(scope, receive, send)
