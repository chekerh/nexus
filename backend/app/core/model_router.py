"""Dynamic model router — selects the best model for each task.

Uses hardware detection + model registry to route tasks to the best
available model, with smart fallbacks and upgrade suggestions.
"""

from __future__ import annotations

from . import hardware_detector as hw
from . import model_registry
from .config import settings

# In-memory cache (refreshed periodically)
_hardware_cache: dict | None = None
_installed_models_cache: list[str] | None = None


def _get_hardware(force_refresh: bool = False) -> dict:
    global _hardware_cache
    if _hardware_cache is None or force_refresh:
        _hardware_cache = hw.detect_all()
    return _hardware_cache


def _get_installed_models(force_refresh: bool = False) -> list[str]:
    global _installed_models_cache
    if _installed_models_cache is None or force_refresh:
        models = hw.detect_ollama_models()
        _installed_models_cache = [m["name"] for m in models]
    return _installed_models_cache


def refresh_cache():
    """Force re-detect hardware and models."""
    global _hardware_cache, _installed_models_cache
    _hardware_cache = hw.detect_all()
    _installed_models_cache = [m["name"] for m in hw.detect_ollama_models()]


def best_model_for_task(
    task: str,
    override_model: str | None = None,
) -> dict:
    """Select the best available model for a task.

    Returns: {
        "model": "gemma4:e4b",
        "provider": "ollama",        # ollama | api | airllm
        "tier": "light",
        "upgrade_suggestion": "gemma4:12b" or None,
        "upgrade_reason": "..." or None,
        "api_key_configured": bool,
        "source": "installed" | "default" | "override",
    }
    """
    # 1. If override is set, use it
    if override_model:
        return _resolve_model(override_model, task, "override")

    # 2. Check env var for task-specific override
    env_override = _env_model_for_task(task)
    if env_override:
        return _resolve_model(env_override, task, "env_override")

    # 3. Dynamic selection (if enabled)
    if settings.DYNAMIC_MODEL_SELECTION:
        result = _select_dynamic(task)
        if result:
            return result

    # 4. Fallback: use configured default model
    return _resolve_model(settings.OLLAMA_MODEL, task, "default")


def _select_dynamic(task: str) -> dict | None:
    """Try to find the best model among installed models for this task."""
    installed = _get_installed_models()
    if not installed:
        return None

    task_req = model_registry.get_task_requirement(task)
    if not task_req:
        return None

    tiers = ["edge", "light", "medium", "heavy"]
    min_idx = tiers.index(task_req.get("min_tier", "edge")) if task_req.get("min_tier") in tiers else 0

    # Score each installed model for this task
    scored = []
    for name in installed:
        info = model_registry.get_model_info(name)
        if not info:
            continue
        model_tier = info.get("tier", "edge")
        model_idx = tiers.index(model_tier) if model_tier in tiers else 0
        if model_idx < min_idx:
            continue  # below minimum tier

        score = model_idx  # prefer higher tier
        if task_req.get("prefers_multilingual") and info.get("multilingual"):
            score += 10  # big bonus for multilingual
        scored.append((score, name, model_tier))

    if not scored:
        return None

    scored.sort(reverse=True)
    best_name = scored[0][1]
    return _resolve_model(best_name, task, "installed")


def _resolve_model(model_name: str, task: str, source: str) -> dict:
    """Resolve a model name into a full result dict."""
    is_api = model_name.startswith("api:")
    provider = "api" if is_api else "ollama"
    clean_name = model_name.replace("api:", "").replace("/", " ") if is_api else model_name

    info = model_registry.get_model_info(model_name)
    tier = info.get("tier", "unknown") if info else "unknown"

    # Check if installed
    installed = False
    if not is_api:
        installed = clean_name in _get_installed_models()

    # Check upgrade
    upgrade = None
    upgrade_reason = None
    if not is_api:
        suggested = model_registry.suggest_upgrade(model_name, task)
        if suggested:
            suggested_info = model_registry.get_model_info(suggested)
            upgrade = suggested
            if suggested_info:
                upgrade_reason = (
                    f"{suggested_info.get('description', suggested)} — "
                    f"recommended over {model_name} for '{task}' tasks."
                )

    api_key_configured = bool(settings.OPENAI_API_KEY)

    return {
        "model": model_name,
        "clean_name": clean_name,
        "provider": provider,
        "tier": tier,
        "upgrade_suggestion": upgrade,
        "upgrade_reason": upgrade_reason,
        "api_key_configured": api_key_configured,
        "source": source,
        "installed": installed,
        "task": task,
        "info": info,
    }


def _env_model_for_task(task: str) -> str | None:
    """Check if there's an env var overriding the model for this task."""
    mapping = {
        "strategist": settings.OLLAMA_ANALYST_MODEL or settings.OLLAMA_MODEL,
        "analyst": settings.OLLAMA_ANALYST_MODEL or settings.OLLAMA_MODEL,
        "caption_style": settings.OLLAMA_STYLE_MODEL or "qwen2.5:0.5b",
        "virality": settings.OLLAMA_MODEL,
        "translation": settings.OLLAMA_MODEL,
        "thumbnails": settings.OLLAMA_STYLE_MODEL or "qwen2.5:0.5b",
        "chat": settings.OLLAMA_MODEL,
    }
    return mapping.get(task)


def get_ollama_model_for_task(task: str) -> str:
    """Return the best Ollama model name for a task.

    This is the main entry point for agents to use. Returns a model name
    string suitable for passing to ollama.chat().
    """
    if settings.DYNAMIC_MODEL_SELECTION:
        result = best_model_for_task(task)
        if result and result.get("provider") == "ollama" and result.get("installed", False):
            return result["model"]
    # Fall back to env var overrides
    env_model = _env_model_for_task(task)
    if env_model:
        return env_model
    return settings.OLLAMA_MODEL


def get_api_fallback_model() -> str | None:
    """Return the API fallback model if an API key is configured."""
    if settings.OPENAI_API_KEY:
        return f"api:{settings.FALLBACK_API_PROVIDER}/{settings.FALLBACK_API_MODEL}"
    return None


def system_recommendation() -> dict:
    """Full system recommendation — used by the setup wizard."""
    hardware = _get_hardware()
    installed = _get_installed_models()
    hardware.get("ram_tier", "light")
    ram_gb = hardware.get("ram_total_gb", 8)

    # Base recommendation
    base_rec = model_registry.recommend_for_hardware(ram_gb)

    # Check what's already installed
    installed_details = model_registry.list_available_models(installed)
    installed_names = [m["name"] for m in installed_details if m.get("installed")]

    # Build a flat model list mixing recommendations + installed info
    recommended_names = base_rec.get("recommended_models", [])
    models_list = []
    seen = set()
    for m in installed_details:
        models_list.append(m)
        seen.add(m["name"])
    for name in recommended_names:
        if name not in seen:
            info = model_registry.get_model_info(name)
            if info:
                models_list.append({"name": name, "installed": False, **info})
                seen.add(name)

    # Generate task-specific recommendations
    task_recs = {}
    for task_key in ["strategist", "analyst", "caption_style", "virality", "translation"]:
        task_recs[task_key] = best_model_for_task(task_key)

    # Check if Ollama needs installing
    needs_ollama = not hardware.get("ollama", {}).get("installed", False)
    needs_models = hardware.get("ollama", {}).get("installed", False) and not hardware.get("ollama", {}).get(
        "running", False
    )
    has_local_models = len(installed_names) > 0
    api_key_ok = bool(settings.OPENAI_API_KEY)

    return {
        "hardware": hardware,
        "recommendation": base_rec,
        "models": models_list,
        "installed_models": installed_details,
        "task_recommendations": task_recs,
        "setup_status": {
            "ollama_installed": hardware.get("ollama", {}).get("installed", False),
            "ollama_running": hardware.get("ollama", {}).get("running", False),
            "local_models_available": has_local_models,
            "api_key_configured": api_key_ok,
            "needs_ollama_install": needs_ollama,
            "needs_ollama_start": needs_models and not has_local_models,
            "needs_models": not has_local_models and not api_key_ok,
            "ffmpeg_installed": hardware.get("ffmpeg_installed", False),
        },
    }
