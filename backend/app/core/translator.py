"""Multi-language caption translation via Ollama."""

import logging
import re

import ollama

logger = logging.getLogger(__name__)

from .config import settings
from .model_router import get_ollama_model_for_task

LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "hi": "Hindi",
    "nl": "Dutch",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "pl": "Polish",
    "uk": "Ukrainian",
    "he": "Hebrew",
    "id": "Indonesian",
}


def is_supported_language(code: str) -> bool:
    return code.lower() in LANGUAGES


def translate_batch(texts: list[str], target_lang: str, source_lang: str = "en") -> list[str] | None:
    if not texts:
        return []
    target = LANGUAGES.get(target_lang, "English")
    source = LANGUAGES.get(source_lang, "English")
    if target_lang == source_lang:
        return texts

    system = (
        f"You are a translator. Translate the following {source} text to {target}. "
        "Preserve any numbers, timestamps, or formatting. "
        "Output only the translations, one per line, in the same order as input. "
        "Do not add explanations or numbering."
    )
    payload = "\n---\n".join(texts)

    try:
        trans_model = get_ollama_model_for_task("translation")
        response = ollama.chat(
            model=trans_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": payload},
            ],
            keep_alive=settings.OLLAMA_KEEP_ALIVE,
            options={"temperature": 0.1, "num_ctx": 4096, "num_predict": 2048},
        )
        content = (response.get("message", {}) or {}).get("content", "").strip()
        if not content:
            return None

        lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
        translated = []
        for i, line in enumerate(lines):
            if i < len(texts):
                translated.append(line)
        if len(translated) != len(texts):
            return None
        return translated
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return None


def translate_transcript(transcript: str, target_lang: str, source_lang: str = "en") -> str | None:
    if target_lang == source_lang:
        return transcript

    lines = transcript.strip().split("\n")
    ts_pattern = re.compile(r"^(\[[^\]]+\]\s+)(.*)$")

    texts = []
    original_lines = []
    for line in lines:
        m = ts_pattern.match(line)
        if m:
            texts.append(m.group(2))
            original_lines.append((m.group(1), m.group(2)))
        else:
            original_lines.append(("", line))

    if not texts:
        return transcript

    translated_texts = translate_batch(texts, target_lang, source_lang)
    if not translated_texts:
        return transcript

    result_lines = []
    ti = 0
    for prefix, orig_text in original_lines:
        if prefix:
            if ti < len(translated_texts) and translated_texts[ti]:
                result_lines.append(f"{prefix}{translated_texts[ti]}")
            else:
                result_lines.append(f"{prefix}{orig_text}")
            ti += 1
        else:
            result_lines.append(orig_text)

    return "\n".join(result_lines)
