import ollama
import json
import re
from pathlib import Path
from typing import Optional, List, Dict
from .config import settings

TIMESTAMP_RE = re.compile(
    r'^\[(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3})\]\s+(.*)$'
)

VIRAL_KEYWORDS = {
    "but": 1.0,
    "however": 1.0,
    "crazy": 1.8,
    "insane": 1.8,
    "secret": 1.8,
    "mistake": 1.8,
    "failed": 1.5,
    "problem": 1.3,
    "crash": 1.4,
    "money": 1.5,
    "million": 1.5,
    "ferrari": 1.8,
    "bugatti": 1.8,
    "lamborghini": 1.8,
    "never": 1.0,
    "watch": 1.0,
    "why": 1.0,
    "how": 0.8,
}

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

def _read_prompt_file(path_str: str) -> str:
    try:
        path = Path(path_str)
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""

def _timestamp_to_seconds(ts: str) -> float:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)

def _parse_segments(transcript: str) -> List[Dict]:
    segments = []
    for line in transcript.splitlines():
        match = TIMESTAMP_RE.match(line.strip())
        if not match:
            continue
        start_s = _timestamp_to_seconds(match.group(1))
        end_s = _timestamp_to_seconds(match.group(2))
        text = match.group(3).strip()
        if text:
            segments.append({"start": start_s, "end": end_s, "text": text})
    return segments

def _score_segment_text(text: str) -> float:
    lowered = text.lower()
    score = 0.0
    for word, weight in VIRAL_KEYWORDS.items():
        if word in lowered:
            score += weight
    if "?" in text:
        score += 0.8
    if "!" in text:
        score += 0.6
    if re.search(r'\$|£|€|\d+', text):
        score += 0.6
    if len(text.split()) >= 12:
        score += 0.5
    return round(score, 2)

def _candidate_windows_summary(segments: List[Dict]) -> str:
    if not segments:
        return ""

    target_len = max(settings.CLIP_MIN_SECONDS, min(30.0, settings.CLIP_MAX_SECONDS))
    scored = []
    for seg in segments:
        score = _score_segment_text(seg["text"])
        if score <= 0:
            continue
        mid = (seg["start"] + seg["end"]) / 2
        start = max(0.0, mid - (target_len / 2))
        end = start + target_len
        scored.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "score": score,
            "reason": seg["text"][:120],
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:8]
    if not top:
        return ""

    lines = ["Candidate windows from heuristic pre-scan (higher score = more likely viral):"]
    for idx, c in enumerate(top, start=1):
        lines.append(
            f"{idx}. {c['start']}s-{c['end']}s | score={c['score']} | cue={c['reason']}"
        )
    return "\n".join(lines)

def _extract_first_json_object(text: str) -> Optional[str]:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    return None

def analyze_transcript(transcript: str) -> Optional[Dict]:
    """Analyzes transcript using local Ollama instance for viral hooks and strategy."""
    strategist_prompt = _read_prompt_file(settings.STRATEGIST_PROMPT_FILE)
    viral_signals_prompt = _read_prompt_file(settings.VIRAL_SIGNALS_FILE)

    system_prompt = (
        "You are an expert viral content strategist. You will receive a transcript with timestamps. "
        "Your goal is to identify 3 high-impact viral hooks. "
        f"Each hook must be between {settings.CLIP_MIN_SECONDS:.0f} and {settings.CLIP_MAX_SECONDS:.0f} seconds long (target 20-35s when possible). "
        "Do not return tiny clips unless there is absolutely no alternative. "
        "Prefer complete narrative beats (setup -> tension -> payoff), not random snippets. "
        "First, provide a 1-2 sentence 'Strategy Insight' about the video's potential. "
        "Then, identify the 3 hooks with exact start/end seconds and captions. "
        "Return your response in this EXACT format: "
        "STRATEGY: <Your insight here>\n"
        "JSON: "
        '{"hooks": [{"start": float, "end": float, "hook_name": "string", "caption": "string"}]}'
    )

    if strategist_prompt:
        system_prompt += "\n\n--- STRATEGIST PLAYBOOK ---\n" + strategist_prompt
    if viral_signals_prompt:
        system_prompt += "\n\n--- VIRAL SIGNALS RUBRIC ---\n" + viral_signals_prompt

    try:
        segments = _parse_segments(transcript)
        cleaned_transcript = "\n".join(
            [f"[{s['start']:.2f} --> {s['end']:.2f}] {s['text']}" for s in segments]
        )
        if not cleaned_transcript:
            cleaned_transcript = transcript
        candidate_summary = _candidate_windows_summary(segments)

        user_payload = cleaned_transcript[:15000]
        if candidate_summary:
            user_payload = f"{candidate_summary}\n\nTranscript:\n{user_payload}"

        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_payload},
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
        json_text = _extract_first_json_object(content)
        if json_text:
            data = json.loads(json_text)
            data['hooks'] = _normalize_hooks(data.get('hooks', []))
            data['strategy_thought'] = strategy
            return data

        return None

    except Exception as e:
        print(f"Ollama analysis failed: {str(e)}")
        return None
