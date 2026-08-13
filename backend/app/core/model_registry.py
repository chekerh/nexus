"""Model registry — defines model tiers, task requirements, and recommended models.

Used by the ModelRouter to select the best model for each task based on
available hardware and locally-installed models.
"""

from __future__ import annotations

from typing import Any

# ── Task definitions ──────────────────────────────────────────
# Each task has a minimum tier requirement and optional multilingual flag.

TASK_REQUIREMENTS: dict[str, dict] = {
    "strategist": {
        "label": "Strategist (clip selection, reasoning)",
        "min_tier": "light",
        "recommended_tier": "medium",
        "prefers_multilingual": True,
        "context_window_min": 8192,
        "description": "Selects high-retention windows, writes captions, plans hook structure.",
    },
    "analyst": {
        "label": "Analyst (transcript analysis, scoring)",
        "min_tier": "light",
        "recommended_tier": "medium",
        "prefers_multilingual": True,
        "context_window_min": 4096,
        "description": "Analyzes transcript content, extracts themes, scores segments.",
    },
    "caption_style": {
        "label": "Caption Style Classifier",
        "min_tier": "edge",
        "recommended_tier": "edge",
        "prefers_multilingual": False,
        "context_window_min": 1024,
        "description": "Classifies phrase-level subtitle styles (neutral, impact, hype, etc).",
    },
    "virality": {
        "label": "Virality Scoring",
        "min_tier": "edge",
        "recommended_tier": "light",
        "prefers_multilingual": False,
        "context_window_min": 2048,
        "description": "Predicts clip performance score 1-100 based on content signals.",
    },
    "translation": {
        "label": "Translation / Dubbing",
        "min_tier": "light",
        "recommended_tier": "medium",
        "prefers_multilingual": True,
        "context_window_min": 4096,
        "description": "Translates captions and content between languages.",
    },
    "thumbnails": {
        "label": "Thumbnail Generation",
        "min_tier": "edge",
        "recommended_tier": "light",
        "prefers_multilingual": False,
        "context_window_min": 2048,
        "description": "Generates and selects thumbnail images.",
    },
    "chat": {
        "label": "General Chat / Q&A",
        "min_tier": "edge",
        "recommended_tier": "light",
        "prefers_multilingual": False,
        "context_window_min": 2048,
        "description": "General-purpose assistant responses.",
    },
}

# ── Model definitions ─────────────────────────────────────────
# Key: Ollama model name (without :tag), or "api:provider/model"

MODEL_DEFINITIONS: dict[str, dict[str, Any]] = {
    "gemma4:e2b": {
        "tier": "edge",
        "size_gb": 5.0,
        "context_window": 128_000,
        "multilingual": True,
        "multimodal": True,
        "license": "Apache 2.0",
        "recommended_ram": 8,
        "description": "Google Gemma 4 E2B — tiny edge model, 140 languages, 128K context.",
    },
    "gemma4:e4b": {
        "tier": "light",
        "size_gb": 6.0,
        "context_window": 128_000,
        "multilingual": True,
        "multimodal": True,
        "license": "Apache 2.0",
        "recommended_ram": 8,
        "description": "Google Gemma 4 E4B — best quality/size for laptops, 140 languages.",
    },
    "gemma4:12b": {
        "tier": "medium",
        "size_gb": 8.0,
        "context_window": 256_000,
        "multilingual": True,
        "multimodal": True,
        "license": "Apache 2.0",
        "recommended_ram": 16,
        "description": "Google Gemma 4 12B — high quality on 16GB machines.",
    },
    "gemma4:26b": {
        "tier": "heavy",
        "size_gb": 18.0,
        "context_window": 256_000,
        "multilingual": True,
        "multimodal": True,
        "license": "Apache 2.0",
        "recommended_ram": 32,
        "description": "Google Gemma 4 26B MoE — frontier quality, 4B active params.",
    },
    "qwen3:30b": {
        "tier": "heavy",
        "size_gb": 18.0,
        "context_window": 128_000,
        "multilingual": True,
        "multimodal": False,
        "license": "Apache 2.0",
        "recommended_ram": 32,
        "description": "Qwen 3 30B — strong multilingual reasoning, 128K context.",
    },
    "phi3": {
        "tier": "light",
        "size_gb": 2.2,
        "context_window": 4096,
        "multilingual": False,
        "multimodal": False,
        "license": "MIT",
        "recommended_ram": 4,
        "description": "Phi-3 — tiny, English-only, fast on any hardware.",
    },
    "qwen2.5:0.5b": {
        "tier": "edge",
        "size_gb": 0.4,
        "context_window": 32_768,
        "multilingual": False,
        "multimodal": False,
        "license": "Apache 2.0",
        "recommended_ram": 2,
        "description": "Qwen 2.5 0.5B — ultra-tiny, fast style classification.",
    },
    "codellama:7b": {
        "tier": "light",
        "size_gb": 3.8,
        "context_window": 16_384,
        "multilingual": False,
        "multimodal": False,
        "license": "LLAMA 2",
        "recommended_ram": 8,
        "description": "Code Llama 7B — code-focused, not ideal for content analysis.",
    },
    "llama-3-3-70b": {
        "tier": "heavy",
        "size_gb": 42.0,
        "context_window": 128_000,
        "multilingual": True,
        "multimodal": False,
        "license": "LLAMA 3.3",
        "recommended_ram": 64,
        "description": "Llama 3.3 70B — very large, needs 64GB+ RAM.",
    },
    # API fallback providers
    "api:openai/gpt-4o-mini": {
        "tier": "heavy",
        "size_gb": 0,
        "context_window": 128_000,
        "multilingual": True,
        "multimodal": True,
        "license": "Proprietary",
        "recommended_ram": 0,
        "description": "OpenAI GPT-4o-mini — cloud API fallback, requires API key.",
    },
    "api:openai/gpt-4o": {
        "tier": "heavy",
        "size_gb": 0,
        "context_window": 128_000,
        "multilingual": True,
        "multimodal": True,
        "license": "Proprietary",
        "recommended_ram": 0,
        "description": "OpenAI GPT-4o — full cloud quality, requires API key.",
    },
}

# ── RAM tier recommendations ──────────────────────────────────
# What to recommend when the user is setting up for the first time.

TIER_RECOMMENDATIONS: dict[str, list[str]] = {
    "edge": ["gemma4:e2b", "qwen2.5:0.5b"],
    "light": ["gemma4:e4b", "phi3", "qwen2.5:0.5b"],
    "medium": ["gemma4:12b", "gemma4:e4b", "qwen2.5:0.5b"],
    "heavy": ["gemma4:26b", "qwen3:30b", "qwen2.5:0.5b"],
}

# Maps storage tier -> the best model for each task
TIER_TASK_DEFAULTS: dict[str, dict[str, str]] = {
    "edge": {
        "strategist": "gemma4:e2b",
        "analyst": "gemma4:e2b",
        "caption_style": "qwen2.5:0.5b",
        "virality": "gemma4:e2b",
        "translation": "gemma4:e2b",
        "thumbnails": "qwen2.5:0.5b",
        "chat": "gemma4:e2b",
    },
    "light": {
        "strategist": "gemma4:e4b",
        "analyst": "gemma4:e4b",
        "caption_style": "qwen2.5:0.5b",
        "virality": "gemma4:e4b",
        "translation": "gemma4:e2b",
        "thumbnails": "qwen2.5:0.5b",
        "chat": "phi3",
    },
    "medium": {
        "strategist": "gemma4:12b",
        "analyst": "gemma4:12b",
        "caption_style": "qwen2.5:0.5b",
        "virality": "gemma4:e4b",
        "translation": "gemma4:12b",
        "thumbnails": "qwen2.5:0.5b",
        "chat": "gemma4:e4b",
    },
    "heavy": {
        "strategist": "gemma4:26b",
        "analyst": "gemma4:26b",
        "caption_style": "qwen2.5:0.5b",
        "virality": "gemma4:e4b",
        "translation": "gemma4:26b",
        "thumbnails": "qwen2.5:0.5b",
        "chat": "qwen3:30b",
    },
}


def get_model_info(model_name: str) -> dict | None:
    """Get the definition for a model by exact name."""
    return MODEL_DEFINITIONS.get(model_name)


def get_task_requirement(task: str) -> dict | None:
    """Get the requirement profile for a task."""
    return TASK_REQUIREMENTS.get(task)


def suggest_upgrade(current_model: str, task: str) -> str | None:
    """If the current model is below recommended tier for a task, suggest a better one."""
    model_info = get_model_info(current_model)
    task_req = get_task_requirement(task)
    if not model_info or not task_req:
        return None
    current_tier = model_info.get("tier", "edge")
    # rank tiers
    tiers = ["edge", "light", "medium", "heavy"]
    current_idx = tiers.index(current_tier) if current_tier in tiers else 0
    min_idx = tiers.index(task_req.get("recommended_tier", "light")) if task_req.get("recommended_tier") in tiers else 1

    if current_idx >= min_idx:
        return None  # no upgrade needed

    # Find best model in the recommended tier
    tier_map = TIER_TASK_DEFAULTS.get(task_req.get("recommended_tier", "light"), {})
    suggested = tier_map.get(task)
    if suggested and suggested != current_model:
        return suggested
    return None


def list_available_models(installed_models: list[str]) -> list[dict]:
    """Return info for all models that are either installed or known."""
    results = []
    seen = set()
    for name in installed_models:
        # strip :latest
        clean = name.replace(":latest", "")
        info = get_model_info(clean)
        if info:
            results.append({"name": clean, "installed": True, **info})
            seen.add(clean)
    # add known but not installed
    for name, info in MODEL_DEFINITIONS.items():
        if name not in seen and not name.startswith("api:"):
            results.append({"name": name, "installed": False, **info})
    return results


def recommend_for_hardware(ram_gb: float, multilingual: bool = True) -> dict:
    """Return a full model recommendation based on available RAM."""
    tier = _ram_tier(ram_gb)
    recommendations = TIER_RECOMMENDATIONS.get(tier, TIER_RECOMMENDATIONS["edge"])
    task_defaults = TIER_TASK_DEFAULTS.get(tier, TIER_TASK_DEFAULTS["edge"])

    return {
        "ram_tier": tier,
        "ram_gb": ram_gb,
        "recommended_models": recommendations,
        "task_defaults": task_defaults,
        "needs_multilingual": multilingual,
        "note": _tier_note(tier),
    }


def _ram_tier(ram_gb: float) -> str:
    if ram_gb < 6:
        return "edge"
    elif ram_gb < 12:
        return "light"
    elif ram_gb < 24:
        return "medium"
    else:
        return "heavy"


def _tier_note(tier: str) -> str:
    notes = {
        "edge": "Limited RAM. Use edge models (E2B, 0.5B). Consider API fallback for complex tasks.",
        "light": "Good for light models. Gemma 4 E4B recommended. 12B models will be tight.",
        "medium": "Can run most models comfortably. 12B is ideal. 26B MoE possible.",
        "heavy": "48GB+ RAM detected. Can run 26B+ models. Consider Gemma 4 26B or qwen3:30b.",
    }
    return notes.get(tier, "")
