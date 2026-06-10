"""Virality Score engine — predicts clip performance 1-100.

Combines heuristic signals with optional AI analysis for a composite score.
Mimics Opus Clip's Virality Score as a signature Nexus-UGC feature.
"""
import json
import re
import ollama
from typing import List, Dict, Optional
from .config import settings

VIRAL_SIGNALS = {
    "hook_question": {"pattern": r"^(why|how|what|when|where|did you|have you|do you)", "weight": 15},
    "hook_number": {"pattern": r"\b\d+", "weight": 10},
    "hook_curiosity": {"pattern": r"\b(secret|never|nobody|everyone|always|worst|best|ultimate|insane|crazy)\b", "weight": 20},
    "hook_contrast": {"pattern": r"\b(but|however|yet|though|instead|unlike)\b", "weight": 12},
    "emotion_money": {"pattern": r"\b(money|cash|million|billion|profit|price|sell|save|cost)\b", "weight": 12},
    "emotion_fear": {"pattern": r"\b(danger|scam|mistake|failed|crash|warning|risk|problem|broken)\b", "weight": 10},
    "emotion_urgency": {"pattern": r"\b(now|today|limited|fast|quick|immediate|hurry|deadline)\b", "weight": 8},
    "engagement_question": {"pattern": r"\?", "weight": 8},
    "engagement_exclamation": {"pattern": r"!", "weight": 5},
    "engagement_you": {"pattern": r"\byou\b", "weight": 5},
    "speech_density": {"pattern": None, "weight": 10},
    "duration_bonus": {"pattern": None, "weight": 5},
}

def _score_text_signals(text: str) -> Dict[str, float]:
    scores = {}
    for name, sig in VIRAL_SIGNALS.items():
        if sig["pattern"] is None:
            continue
        count = len(re.findall(sig["pattern"], text.lower()))
        scores[name] = min(100, count * sig["weight"])
    return scores

def _score_duration(duration: float) -> float:
    if 15 <= duration <= 35:
        return 85
    elif 10 <= duration <= 45:
        return 60
    elif duration < 10:
        return 30
    else:
        return 40

def _score_speech_density(density: float) -> float:
    return min(100, density * 100)

def _heuristic_virality(text: str, duration: float, speech_density: float) -> float:
    signal_scores = _score_text_signals(text)
    base = sum(signal_scores.values()) / max(1, len(signal_scores))
    dur_score = _score_duration(duration)
    density_score = _score_speech_density(speech_density)
    return round(min(100, base * 0.5 + dur_score * 0.25 + density_score * 0.25), 1)

def _ai_virality_analysis(texts: List[str]) -> Optional[List[float]]:
    if not texts:
        return None
    try:
        system = (
            "You are a viral clip analyst. Rate each clip's virality potential from 1-100. "
            "Consider: hook strength, emotional triggers, curiosity gap, audience retention. "
            "Output strict JSON: {\"scores\": [score1, score2, ...]}"
        )
        payload_lines = [f"Clip {i+1}: {t[:300]}" for i, t in enumerate(texts)]
        user = "\n".join(payload_lines)

        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            keep_alive=settings.OLLAMA_KEEP_ALIVE,
            options={"temperature": 0.1, "num_ctx": 4096, "num_predict": 512},
        )
        content = (response.get("message", {}) or {}).get("content", "").strip()
        m = re.search(r"\{[\s\S]*\}", content)
        if m:
            parsed = json.loads(m.group(0))
            scores = parsed.get("scores", [])
            if scores and len(scores) == len(texts):
                return [min(100, max(1, float(s))) for s in scores]
        return None
    except Exception:
        return None

def score_clip(text: str, duration: float, speech_density: float = 0.5) -> float:
    return _heuristic_virality(text, duration, speech_density)

def score_clips(hooks: List[Dict], transcript: str = "") -> List[Dict]:
    if not hooks:
        return []

    scored = []
    for hook in hooks:
        text = hook.get("caption", "") or hook.get("hook_name", "")
        duration = (hook.get("end", 0) or 0) - (hook.get("start", 0) or 0)
        if duration <= 0:
            duration = 30.0
        score = _heuristic_virality(text, duration, 0.7)
        scored.append({
            **hook,
            "virality_score": score,
            "virality_breakdown": _score_text_signals(text),
        })

    texts = [h.get("caption", "") or h.get("hook_name", "") for h in hooks]
    ai_scores = _ai_virality_analysis(texts)
    if ai_scores:
        for i, s in enumerate(ai_scores):
            if i < len(scored):
                hybrid = round(scored[i]["virality_score"] * 0.4 + s * 0.6, 1)
                scored[i]["virality_score"] = hybrid
                scored[i]["virality_ai_score"] = s

    return scored
