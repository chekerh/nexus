import ollama
import json
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Tuple
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

MIN_SCENE_SCORE = 0.35

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
            "confidence": round(_to_float(hook.get("confidence", 0.5), 0.5), 2),
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

def _video_duration_from_path(video_path: Optional[str]) -> float:
    if not video_path:
        return 0.0
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return _to_float(result.stdout.strip(), 0.0)
    except Exception:
        return 0.0

def _detect_scene_cuts(video_path: Optional[str], threshold: float = MIN_SCENE_SCORE) -> List[float]:
    """Detect candidate scene cuts using ffmpeg scene filter."""
    if not video_path:
        return []
    try:
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-filter:v", f"select=gt(scene\\,{threshold}),showinfo",
            "-f", "null",
            "-",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        stderr = result.stderr or ""
        points = []
        for m in re.finditer(r"pts_time:([0-9]+(?:\.[0-9]+)?)", stderr):
            points.append(_to_float(m.group(1), 0.0))
        # de-duplicate nearby points
        points.sort()
        deduped = []
        for p in points:
            if not deduped or abs(p - deduped[-1]) > 0.35:
                deduped.append(round(p, 2))
        return deduped
    except Exception:
        return []

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

def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))

def _candidate_from_segment(seg: Dict, target_len: float, total_duration: float) -> Tuple[float, float]:
    mid = (seg["start"] + seg["end"]) / 2
    start = max(0.0, mid - (target_len / 2))
    end = start + target_len
    if total_duration > 0 and end > total_duration:
        end = total_duration
        start = max(0.0, end - target_len)
    return round(start, 2), round(end, 2)

def _speech_metrics(start: float, end: float, segments: List[Dict]) -> Tuple[float, float]:
    duration = max(0.001, end - start)
    spoken_seconds = 0.0
    spoken_words = 0
    for seg in segments:
        ov = _overlap(start, end, seg["start"], seg["end"])
        if ov <= 0:
            continue
        spoken_seconds += ov
        words = len(re.findall(r"\b\w+\b", seg["text"]))
        seg_duration = max(0.001, seg["end"] - seg["start"])
        spoken_words += int(words * (ov / seg_duration))

    density = spoken_seconds / duration
    wps = spoken_words / duration
    return round(density, 3), round(wps, 3)

def _scene_bonus(start: float, end: float, scene_cuts: List[float]) -> float:
    if not scene_cuts:
        return 0.0
    start_near = any(abs(c - start) <= 2.0 for c in scene_cuts)
    end_near = any(abs(c - end) <= 2.0 for c in scene_cuts)
    bonus = 0.0
    if start_near:
        bonus += 0.8
    if end_near:
        bonus += 0.5
    return bonus

def _build_candidates(segments: List[Dict], scene_cuts: List[float], total_duration: float) -> List[Dict]:
    if not segments:
        return []

    target_len = max(settings.CLIP_MIN_SECONDS, min(28.0, settings.CLIP_MAX_SECONDS))
    candidates = []
    for seg in segments:
        text_score = _score_segment_text(seg["text"])
        if text_score <= 0:
            continue

        start, end = _candidate_from_segment(seg, target_len, total_duration)
        density, wps = _speech_metrics(start, end, segments)
        score = (
            text_score
            + (density * 2.0)
            + min(wps, 3.0) * 0.5
            + _scene_bonus(start, end, scene_cuts)
        )

        candidates.append({
            "start": start,
            "end": end,
            "score": round(score, 2),
            "text_score": text_score,
            "speech_density": density,
            "words_per_sec": wps,
            "reason": seg["text"][:120],
        })

    # Rank and remove highly overlapping near-duplicates.
    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected = []
    for cand in candidates:
        too_close = False
        for kept in selected:
            ov = _overlap(cand["start"], cand["end"], kept["start"], kept["end"])
            min_d = min(cand["end"] - cand["start"], kept["end"] - kept["start"])
            if min_d > 0 and ov / min_d > 0.75:
                too_close = True
                break
        if not too_close:
            selected.append(cand)
        if len(selected) >= 12:
            break

    for idx, cand in enumerate(selected, start=1):
        cand["id"] = idx
    return selected

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

def _candidate_windows_summary_v3(candidates: List[Dict], scene_cuts: List[float]) -> str:
    if not candidates:
        return ""
    lines = [
        "Candidate windows from hybrid scorer (semantic + speech density + scene boundaries):",
        "You should prefer these windows unless transcript evidence strongly disagrees.",
    ]
    for c in candidates:
        lines.append(
            f"id={c['id']} | {c['start']}s-{c['end']}s | score={c['score']} | density={c['speech_density']} | wps={c['words_per_sec']} | cue={c['reason']}"
        )
    if scene_cuts:
        preview = ", ".join([f"{x}s" for x in scene_cuts[:20]])
        lines.append(f"Detected scene cuts (first 20): {preview}")
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

def _snap_hooks_to_candidates(hooks: List[Dict], candidates: List[Dict]) -> List[Dict]:
    if not hooks or not candidates:
        return hooks

    result = []
    for hook in hooks:
        s = _to_float(hook.get("start", 0.0), 0.0)
        e = _to_float(hook.get("end", 0.0), 0.0)
        if e < s:
            s, e = e, s

        best = None
        best_ov = -1.0
        for c in candidates:
            ov = _overlap(s, e, c["start"], c["end"])
            if ov > best_ov:
                best_ov = ov
                best = c

        if best and best_ov <= 0:
            # No overlap: snap by nearest midpoint.
            mid = (s + e) / 2
            best = min(candidates, key=lambda c: abs(((c["start"] + c["end"]) / 2) - mid))

        if best:
            hook["start"] = best["start"]
            hook["end"] = best["end"]
            if "confidence" not in hook:
                hook["confidence"] = round(min(0.95, max(0.35, best["score"] / 10.0)), 2)

        result.append(hook)

    return result

def analyze_transcript(transcript: str, video_path: Optional[str] = None) -> Optional[Dict]:
    """Analyzes transcript using local Ollama instance for viral hooks and strategy."""
    strategist_prompt = _read_prompt_file(settings.STRATEGIST_PROMPT_FILE)
    viral_signals_prompt = _read_prompt_file(settings.VIRAL_SIGNALS_FILE)

    system_prompt = (
        "You are an expert viral content strategist. You will receive a transcript with timestamps. "
        "Your goal is to identify 3 high-impact viral hooks. "
        f"Each hook must be between {settings.CLIP_MIN_SECONDS:.0f} and {settings.CLIP_MAX_SECONDS:.0f} seconds long (target 20-35s when possible). "
        "Do not return tiny clips unless there is absolutely no alternative. "
        "Prefer complete narrative beats (setup -> tension -> payoff), not random snippets. "
        "You will receive candidate windows with quality scores: prefer selecting from them. "
        "First, provide a 1-2 sentence 'Strategy Insight' about the video's potential. "
        "Then, identify the 3 hooks with exact start/end seconds and captions. "
        "Return your response in this EXACT format: "
        "STRATEGY: <Your insight here>\n"
        "JSON: "
        '{"hooks": [{"start": float, "end": float, "hook_name": "string", "caption": "string", "confidence": float}]}'
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
        total_duration = _video_duration_from_path(video_path)
        scene_cuts = _detect_scene_cuts(video_path)
        candidates = _build_candidates(segments, scene_cuts, total_duration)
        candidate_summary = _candidate_windows_summary_v3(candidates, scene_cuts)
        if not candidate_summary:
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
            hooks = data.get('hooks', [])
            hooks = _snap_hooks_to_candidates(hooks, candidates)
            data['hooks'] = _normalize_hooks(hooks)
            data['strategy_thought'] = strategy
            return data

        return None

    except Exception as e:
        print(f"Ollama analysis failed: {str(e)}")
        return None
