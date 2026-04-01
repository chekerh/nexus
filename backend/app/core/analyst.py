import ollama
import json
import re
from typing import Optional, List, Dict
from .config import settings

def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _normalize_hooks(raw_hooks: List[Dict]) -> List[Dict]:
    """Normalize and enforce minimum/maximum clip durations."""
    normalized = []
    min_len = settings.CLIP_MIN_SECONDS
    max_len = settings.CLIP_MAX_SECONDS

    for i, hook in enumerate(raw_hooks or []):
        start = _to_float(hook.get("start", 0.0), 0.0)
        end = _to_float(hook.get("end", start), start)
        if end < start:
            start, end = end, start

        duration = end - start
        if duration < min_len:
            end = start + min_len
            duration = min_len

        if duration > max_len:
            end = start + max_len

        normalized.append({
            "start": round(max(0.0, start), 2),
            "end": round(max(0.0, end), 2),
            "hook_name": hook.get("hook_name") or f"Hook {i + 1}",
            "caption": hook.get("caption") or "",
        })

    return normalized

def analyze_transcript(transcript: str) -> Optional[Dict]:
    """Analyzes transcript using local Ollama instance for viral hooks and strategy."""
    system_prompt = (
        "You are an expert viral content strategist. You will receive a transcript with timestamps. "
        "Your goal is to identify 3 high-impact viral hooks. "
        f"Each hook must be between {settings.CLIP_MIN_SECONDS:.0f} and {settings.CLIP_MAX_SECONDS:.0f} seconds long (target 20-35s when possible). "
        "Do not return tiny clips unless there is absolutely no alternative. "
        "First, provide a 1-2 sentence 'Strategy Insight' about the video's potential. "
        "Then, identify the 3 hooks with exact start/end seconds and captions. "
        "Return your response in this EXACT format: "
        "STRATEGY: <Your insight here>\n"
        "JSON: "
        '{"hooks": [{"start": float, "end": float, "hook_name": "string", "caption": "string"}]}'
    )

    try:
        processed_transcript = transcript[:15000] 

        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': processed_transcript},
            ]
        )
        content = response['message']['content'].strip()

        # Extract Strategy and JSON
        strategy = "Analyzing content structure..."
        if "STRATEGY:" in content:
            strategy_match = re.search(r'STRATEGY:(.*?)(JSON:|$)', content, re.DOTALL)
            if strategy_match:
                strategy = strategy_match.group(1).strip()

        # We'll return the strategy along with the hooks
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            data['hooks'] = _normalize_hooks(data.get('hooks', []))
            data['strategy_thought'] = strategy
            return data

        return None

    except Exception as e:
        print(f"Ollama analysis failed: {str(e)}")
        return None
