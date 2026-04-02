import os
import subprocess
import re
import json
import ollama
from typing import List, Dict, Optional
from .config import settings

TRANSCRIPT_LINE_RE = re.compile(r'^\[(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3})\]\s+(.*)$')

SUBTITLE_PRESETS = {
    "bold_center": "Alignment=2,FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H80000000,Bold=1,Outline=2,Shadow=0,MarginV=28",
    "tiktok_pop": "Alignment=2,FontName=Arial,FontSize=18,PrimaryColour=&H0000F9FF,OutlineColour=&H00000000,BackColour=&H80000000,Bold=1,Outline=3,Shadow=0,MarginV=34",
    "clean_minimal": "Alignment=2,FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H50000000,Bold=0,Outline=1,Shadow=0,MarginV=24",
}

FORMAT_PRESET_FILTERS = {
    "source": [],
    "vertical_9_16": ["scale=1080:1920:force_original_aspect_ratio=increase", "crop=1080:1920"],
    "square_1_1": ["scale=1080:1080:force_original_aspect_ratio=increase", "crop=1080:1080"],
    "portrait_4_5": ["scale=1080:1350:force_original_aspect_ratio=increase", "crop=1080:1350"],
}

CAPTION_STYLES = {
    "neutral": {"className": "cap-neutral"},
    "impact": {"className": "cap-impact"},
    "question": {"className": "cap-question"},
    "money": {"className": "cap-money"},
    "warning": {"className": "cap-warning"},
    "hype": {"className": "cap-hype"},
}

STYLE_KEYWORDS = {
    "money": {"money", "million", "rich", "price", "cash", "profit", "sell"},
    "warning": {"warning", "danger", "scam", "failed", "mistake", "risk", "crash"},
    "hype": {"crazy", "insane", "viral", "best", "huge", "ultimate", "secret"},
}

STYLE_IDS = ["neutral", "impact", "question", "money", "warning", "hype"]
STYLE_ROTATION = ["impact", "question", "money", "warning", "hype", "neutral"]

_FFMPEG_FILTER_CACHE: Optional[set[str]] = None

def sanitize_filename(filename: str) -> str:
    """Removes special characters and spaces from filenames."""
    # Remove file extension first
    name = os.path.splitext(filename)[0]
    # Replace spaces and special chars with underscores
    clean_name = re.sub(r'[^\w\-]', '_', name)
    return clean_name

def get_video_duration(video_path: str) -> float:
    """Returns media duration in seconds using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0

def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def _ts_to_seconds(ts: str) -> float:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)

def _seconds_to_srt(seconds: float) -> str:
    total_ms = int(round(max(0.0, seconds) * 1000))
    h = total_ms // 3600000
    total_ms %= 3600000
    m = total_ms // 60000
    total_ms %= 60000
    s = total_ms // 1000
    ms = total_ms % 1000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"

def _seconds_to_vtt(seconds: float) -> str:
    total_ms = int(round(max(0.0, seconds) * 1000))
    h = total_ms // 3600000
    total_ms %= 3600000
    m = total_ms // 60000
    total_ms %= 60000
    s = total_ms // 1000
    ms = total_ms % 1000
    return f"{h:02}:{m:02}:{s:02}.{ms:03}"

def _seconds_to_ass(seconds: float) -> str:
    centis = int(round(max(0.0, seconds) * 100))
    h = centis // 360000
    centis %= 360000
    m = centis // 6000
    centis %= 6000
    s = centis // 100
    cs = centis % 100
    return f"{h}:{m:02}:{s:02}.{cs:02}"

def _escape_filter_path(path: str) -> str:
    # ffmpeg filter parser escaping
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

def _split_caption_words(text: str, max_words: int) -> List[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text]
    chunks = []
    for i in range(0, len(words), max_words):
        chunks.append(" ".join(words[i:i + max_words]))
    return chunks

def _highlight_caption_words(text: str, highlight_words: set[str]) -> str:
    if not highlight_words:
        return text

    tokens = text.split()
    styled_tokens = []
    for token in tokens:
        normalized = re.sub(r"[^a-zA-Z0-9]", "", token).lower()
        if normalized in highlight_words:
            styled_tokens.append(r"{\c&H00A5FF&\b1\fs58}" + token + r"{\r}")
        else:
            styled_tokens.append(token)
    return " ".join(styled_tokens)

def _choose_caption_style(text: str) -> str:
    lowered = text.lower()
    if "?" in text or lowered.startswith("why") or lowered.startswith("how"):
        return "question"
    if any(k in lowered for k in STYLE_KEYWORDS["money"]):
        return "money"
    if any(k in lowered for k in STYLE_KEYWORDS["warning"]):
        return "warning"
    if any(k in lowered for k in STYLE_KEYWORDS["hype"]):
        return "hype"
    if "!" in text:
        return "impact"
    return "neutral"

def _choose_style_model() -> str:
    model = (settings.OLLAMA_STYLE_MODEL or settings.OLLAMA_ANALYST_MODEL or settings.OLLAMA_MODEL).strip()
    if settings.PROCESSING_PROFILE == "eco" and not settings.OLLAMA_STYLE_MODEL:
        return "qwen2.5:0.5b"
    return model

def _infer_caption_styles_with_ai(texts: List[str]) -> List[str]:
    if not texts:
        return []

    style_model = _choose_style_model()
    system = (
        "You are a short-video subtitle style classifier. "
        "For each input caption text, output one style from this set only: "
        "neutral, impact, question, money, warning, hype. "
        "Output strict JSON only in this format: {\"styles\": [\"style1\", \"style2\", ...]}."
    )
    payload_lines = [f"{i+1}. {t}" for i, t in enumerate(texts)]
    user = "Caption lines:\n" + "\n".join(payload_lines)

    try:
        response = ollama.chat(
            model=style_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            keep_alive=settings.OLLAMA_KEEP_ALIVE,
            options={
                "temperature": 0.1,
                "num_ctx": max(512, settings.OLLAMA_STYLE_NUM_CTX),
                "num_predict": max(32, settings.OLLAMA_STYLE_NUM_PREDICT),
            },
        )
        content = (response.get("message", {}) or {}).get("content", "").strip()
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            return []
        parsed = json.loads(match.group(0))
        styles = parsed.get("styles", []) if isinstance(parsed, dict) else []
        clean_styles = []
        for s in styles:
            v = str(s).strip().lower()
            clean_styles.append(v if v in STYLE_IDS else "neutral")
        return clean_styles
    except Exception:
        return []

def _parse_transcript_segments(transcript: Optional[str]) -> List[Dict]:
    if not transcript:
        return []
    segments: List[Dict] = []
    for line in transcript.splitlines():
        match = TRANSCRIPT_LINE_RE.match(line.strip())
        if not match:
            continue
        start = _ts_to_seconds(match.group(1))
        end = _ts_to_seconds(match.group(2))
        text = match.group(3).strip()
        if end > start and text:
            segments.append({"start": start, "end": end, "text": text})
    return segments

def _write_clip_srt(srt_path: str, segments: List[Dict], clip_start: float, clip_end: float, max_words: int) -> bool:
    clip_entries: List[Dict] = []
    for seg in segments:
        overlap_start = max(clip_start, seg["start"])
        overlap_end = min(clip_end, seg["end"])
        if overlap_end <= overlap_start:
            continue

        relative_start = overlap_start - clip_start
        relative_end = overlap_end - clip_start
        words_chunks = _split_caption_words(seg["text"], max_words)
        chunk_duration = max(0.35, (relative_end - relative_start) / max(1, len(words_chunks)))

        for idx, chunk in enumerate(words_chunks):
            chunk_start = relative_start + idx * chunk_duration
            chunk_end = min(relative_end, chunk_start + chunk_duration)
            if chunk_end > chunk_start:
                clip_entries.append({
                    "start": chunk_start,
                    "end": chunk_end,
                    "text": chunk,
                })

    if not clip_entries:
        return False

    lines: List[str] = []
    for i, entry in enumerate(clip_entries, start=1):
        lines.append(str(i))
        lines.append(f"{_seconds_to_srt(entry['start'])} --> {_seconds_to_srt(entry['end'])}")
        lines.append(entry["text"])
        lines.append("")

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    return True

def _ass_style_name(style_id: str) -> str:
    mapping = {
        "neutral": "CapNeutral",
        "impact": "CapImpact",
        "question": "CapQuestion",
        "money": "CapMoney",
        "warning": "CapWarning",
        "hype": "CapHype",
    }
    return mapping.get(style_id, "CapNeutral")

def _ass_effect_text(style_id: str, text: str) -> str:
    if style_id in {"impact", "hype"}:
        return r"{\fscx118\fscy118\t(0,180,\fscx100\fscy100)}" + text
    if style_id == "question":
        return r"{\fad(80,40)}" + text
    if style_id == "warning":
        return r"{\bord3}" + text
    return text

def _pick_alternate_style(current: str, cue_text: str, position: int) -> str:
    text = (cue_text or "").lower()
    if "?" in cue_text:
        return "question"
    if any(k in text for k in STYLE_KEYWORDS["money"]):
        return "money"
    if any(k in text for k in STYLE_KEYWORDS["warning"]):
        return "warning"
    for i in range(len(STYLE_ROTATION)):
        candidate = STYLE_ROTATION[(position + i) % len(STYLE_ROTATION)]
        if candidate != current:
            return candidate
    return "neutral"

def _diversify_style_sequence(entries: List[Dict], min_variety: int) -> None:
    if not entries:
        return

    # Break long streaks of same style.
    streak_style = None
    streak = 0
    for i, entry in enumerate(entries):
        style = entry.get("style", "neutral")
        if style == streak_style:
            streak += 1
        else:
            streak_style = style
            streak = 1
        if streak >= 3:
            entry["style"] = _pick_alternate_style(style, entry.get("text", ""), i)
            streak_style = entry["style"]
            streak = 1

    # Ensure minimum global variety so captions don't feel static.
    unique_styles = {e.get("style", "neutral") for e in entries}
    target = max(1, min(6, min_variety))
    if len(unique_styles) >= target:
        return

    needed = target - len(unique_styles)
    idx = 0
    while needed > 0 and idx < len(entries):
        cur = entries[idx].get("style", "neutral")
        alt = _pick_alternate_style(cur, entries[idx].get("text", ""), idx)
        if alt not in unique_styles:
            entries[idx]["style"] = alt
            unique_styles.add(alt)
            needed -= 1
        idx += 2

def _assign_visual_variants(entries: List[Dict]) -> None:
    for i, entry in enumerate(entries):
        style = entry.get("style", "neutral")
        variant_base = 1 + (i % 4)
        if style == "warning":
            variant_base = 4 if i % 2 == 0 else 2
        elif style == "money":
            variant_base = 3 if i % 2 == 0 else 1
        entry["variant"] = variant_base
        entry["cue_index"] = i + 1

def _write_clip_ass(ass_path: str, segments: List[Dict], clip_start: float, clip_end: float, max_words: int, font_size: int, process_id: Optional[str] = None, thought_callback=None, clip_index: int = 0) -> bool:
    clip_entries: List[Dict] = []
    for seg in segments:
        overlap_start = max(clip_start, seg["start"])
        overlap_end = min(clip_end, seg["end"])
        if overlap_end <= overlap_start:
            continue

        relative_start = overlap_start - clip_start
        relative_end = overlap_end - clip_start
        words_chunks = _split_caption_words(seg["text"], max_words)
        chunk_duration = max(0.30, (relative_end - relative_start) / max(1, len(words_chunks)))

        for idx, chunk in enumerate(words_chunks):
            chunk_start = relative_start + idx * chunk_duration
            chunk_end = min(relative_end, chunk_start + chunk_duration)
            if chunk_end > chunk_start:
                clip_entries.append({
                    "start": chunk_start,
                    "end": chunk_end,
                    "text": chunk,
                    "style": _choose_caption_style(chunk),
                })

    if not clip_entries:
        return False

    mode = (settings.CAPTION_STYLE_MODE or "hybrid").strip().lower()
    ai_limit = max(0, settings.CAPTION_STYLE_AI_MAX_CUES)
    if mode in {"ai", "hybrid"} and ai_limit > 0:
        ai_indexes = [
            idx for idx, cue in enumerate(clip_entries)
            if mode == "ai" or cue.get("style") == "neutral"
        ][:ai_limit]
        ai_texts = [clip_entries[idx]["text"] for idx in ai_indexes]
        ai_styles = _infer_caption_styles_with_ai(ai_texts)
        if ai_styles:
            for idx, style in zip(ai_indexes, ai_styles):
                if style in STYLE_IDS:
                    clip_entries[idx]["style"] = style
            if thought_callback:
                thought_callback(process_id, f"Caption Engine: Animated subtitle styles updated by AI on clip {clip_index} ({len(ai_styles)} cues).")

    _diversify_style_sequence(clip_entries, settings.CAPTION_STYLE_MIN_VARIETY)
    _assign_visual_variants(clip_entries)
    if thought_callback and clip_entries:
        unique_styles = len({c.get("style", "neutral") for c in clip_entries})
        thought_callback(process_id, f"Caption Engine: Clip {clip_index} animated styles diversified ({unique_styles} style groups).")

    ass_lines = [
        "[Script Info]",
        "Title: Nexus UGC Captions",
        "ScriptType: v4.00+",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
        "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        f"Style: CapNeutral,Arial,{font_size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,2,0,2,40,40,56,1",
        f"Style: CapImpact,Arial,{font_size + 2},&H00FFFFFF,&H0000FFFF,&H00132A53,&H80201010,1,0,0,0,100,100,0,0,1,2,0,2,40,40,56,1",
        f"Style: CapQuestion,Arial,{font_size + 1},&H00FFD8D8,&H0000FFFF,&H003A2E71,&H80201010,1,0,0,0,100,100,0,0,1,2,0,2,40,40,56,1",
        f"Style: CapMoney,Arial,{font_size + 2},&H00C8FFB7,&H0000FFFF,&H001B4A1A,&H80201010,1,0,0,0,100,100,0,0,1,2,0,2,40,40,56,1",
        f"Style: CapWarning,Arial,{font_size + 2},&H00D9D2FF,&H0000FFFF,&H0025147A,&H80201010,1,0,0,0,100,100,0,0,1,2,0,2,40,40,56,1",
        f"Style: CapHype,Arial,{font_size + 3},&H00B3F5FF,&H0000FFFF,&H000F3B73,&H80201010,1,0,0,0,100,100,0,0,1,2,0,2,40,40,56,1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]

    for entry in clip_entries:
        style_id = entry.get("style", "neutral")
        text = _ass_effect_text(style_id, entry["text"])
        ass_lines.append(
            f"Dialogue: 0,{_seconds_to_ass(entry['start'])},{_seconds_to_ass(entry['end'])},{_ass_style_name(style_id)},,0,0,0,,{text}"
        )

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ass_lines) + "\n")
    return True

def _get_format_preset_filters() -> List[str]:
    preset = (settings.CLIP_FORMAT_PRESET or "source").strip().lower()
    return list(FORMAT_PRESET_FILTERS.get(preset, FORMAT_PRESET_FILTERS["source"]))

def _ffmpeg_supports_filter(filter_name: str) -> bool:
    global _FFMPEG_FILTER_CACHE
    try:
        if _FFMPEG_FILTER_CACHE is None:
            result = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True)
            names = set()
            for line in (result.stdout or "").splitlines():
                parts = line.split()
                if len(parts) >= 4:
                    names.add(parts[1])
            _FFMPEG_FILTER_CACHE = names
        return filter_name in (_FFMPEG_FILTER_CACHE or set())
    except Exception:
        return False

def _build_ffmpeg_command(video_path: str, start: float, duration: float, output_path: str, subtitle_path: Optional[str], transcript_segments: List[Dict], process_id: str = None, thought_callback=None, clip_index: int = 0, enable_format: bool = True, enable_transitions: bool = True, enable_zoom: bool = True, enable_subtitles: bool = True, animated_captions: bool = True) -> List[str]:
    cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", video_path, "-t", str(duration)]
    vf_parts = _get_format_preset_filters() if enable_format else []
    af_parts = []

    if enable_transitions and settings.CLIP_ENABLE_TRANSITIONS:
        fade_len = max(0.05, min(settings.CLIP_FADE_SECONDS, max(0.05, duration / 3)))
        fade_out_start = max(0.0, duration - fade_len)
        vf_parts.extend([
            f"fade=t=in:st=0:d={fade_len}",
            f"fade=t=out:st={fade_out_start}:d={fade_len}",
        ])
        af_parts.extend([
            f"afade=t=in:st=0:d={fade_len}",
            f"afade=t=out:st={fade_out_start}:d={fade_len}",
        ])

    if enable_zoom and settings.CLIP_ENABLE_SUBTLE_ZOOM:
        zoom_max = max(1.0, settings.CLIP_ZOOM_MAX)
        vf_parts.append(
            f"scale=iw*{zoom_max}:ih*{zoom_max},crop=iw/{zoom_max}:ih/{zoom_max}"
        )

    if enable_subtitles and settings.CLIP_ENABLE_SUBTITLES and transcript_segments and subtitle_path:
        subtitle_written = False
        if animated_captions and settings.CLIP_ENABLE_ANIMATED_CAPTIONS:
            subtitle_written = _write_clip_ass(
                subtitle_path,
                transcript_segments,
                clip_start=start,
                clip_end=start + duration,
                max_words=max(3, settings.CLIP_SUBTITLE_MAX_WORDS),
                font_size=max(26, settings.CLIP_CAPTION_FONT_SIZE),
                process_id=process_id,
                thought_callback=thought_callback,
                clip_index=clip_index,
            )
        else:
            subtitle_written = _write_clip_srt(
                subtitle_path,
                transcript_segments,
                clip_start=start,
                clip_end=start + duration,
                max_words=max(3, settings.CLIP_SUBTITLE_MAX_WORDS),
            )

        if subtitle_written:
            preset = SUBTITLE_PRESETS.get(settings.CLIP_SUBTITLE_PRESET, SUBTITLE_PRESETS["bold_center"])
            escaped_sub_path = _escape_filter_path(subtitle_path)
            if animated_captions and settings.CLIP_ENABLE_ANIMATED_CAPTIONS:
                vf_parts.append(f"subtitles='{escaped_sub_path}'")
            else:
                vf_parts.append(f"subtitles='{escaped_sub_path}':force_style='{preset}'")
            if thought_callback:
                mode = "animated" if (animated_captions and settings.CLIP_ENABLE_ANIMATED_CAPTIONS) else "static"
                thought_callback(process_id, f"Caption Engine: Burn-in subtitles enabled for clip {clip_index} ({mode} / {settings.CLIP_SUBTITLE_PRESET}).")

    if vf_parts:
        cmd.extend(["-vf", ",".join(vf_parts)])
    if af_parts:
        cmd.extend(["-af", ",".join(af_parts)])

    encoder = (settings.VIDEO_ENCODER or "auto").strip().lower()
    if encoder == "auto":
        encoder = "h264_videotoolbox"

    threads = max(1, settings.VIDEO_THREADS)
    if encoder == "h264_videotoolbox":
        cmd.extend(["-c:v", "h264_videotoolbox", "-b:v", "5M", "-maxrate", "6M", "-bufsize", "10M"])
    else:
        profile = (settings.PROCESSING_PROFILE or "balanced").strip().lower()
        preset = "veryfast" if profile == "eco" else "ultrafast"
        cmd.extend(["-c:v", "libx264", "-preset", preset, "-crf", "23", "-threads", str(threads)])

    cmd.extend(["-c:a", "aac", "-b:a", "128k", output_path])
    return cmd

def _run_ffmpeg_command(cmd: List[str], process_id: str = None, active_pids: dict = None) -> tuple[bool, str]:
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=os.setsid,
    )
    if process_id and active_pids is not None:
        active_pids[process_id] = process.pid
    output_lines = []
    if process.stdout:
        for line in process.stdout:
            output_lines.append(line.rstrip())
    process.wait()
    if process_id and active_pids is not None:
        active_pids.pop(process_id, None)
    return process.returncode == 0, "\n".join(output_lines)

def _write_clip_vtt(vtt_path: str, segments: List[Dict], clip_start: float, clip_end: float, max_words: int) -> bool:
    clip_entries: List[Dict] = []
    for seg in segments:
        overlap_start = max(clip_start, seg["start"])
        overlap_end = min(clip_end, seg["end"])
        if overlap_end <= overlap_start:
            continue

        relative_start = overlap_start - clip_start
        relative_end = overlap_end - clip_start
        words_chunks = _split_caption_words(seg["text"], max_words)
        chunk_duration = max(0.35, (relative_end - relative_start) / max(1, len(words_chunks)))

        for idx, chunk in enumerate(words_chunks):
            chunk_start = relative_start + idx * chunk_duration
            chunk_end = min(relative_end, chunk_start + chunk_duration)
            if chunk_end > chunk_start:
                clip_entries.append({
                    "start": chunk_start,
                    "end": chunk_end,
                    "text": chunk,
                })

    if not clip_entries:
        return False

    lines = ["WEBVTT", ""]
    for entry in clip_entries:
        lines.append(f"{_seconds_to_vtt(entry['start'])} --> {_seconds_to_vtt(entry['end'])}")
        lines.append(entry["text"])
        lines.append("")

    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")
    return True

def _write_clip_cues_json(cues_path: str, segments: List[Dict], clip_start: float, clip_end: float, max_words: int, process_id: Optional[str] = None, thought_callback=None, clip_index: int = 0) -> bool:
    cues: List[Dict] = []
    for seg in segments:
        overlap_start = max(clip_start, seg["start"])
        overlap_end = min(clip_end, seg["end"])
        if overlap_end <= overlap_start:
            continue

        relative_start = overlap_start - clip_start
        relative_end = overlap_end - clip_start
        words_chunks = _split_caption_words(seg["text"], max_words)
        chunk_duration = max(0.35, (relative_end - relative_start) / max(1, len(words_chunks)))

        for idx, chunk in enumerate(words_chunks):
            chunk_start = relative_start + idx * chunk_duration
            chunk_end = min(relative_end, chunk_start + chunk_duration)
            if chunk_end > chunk_start:
                cues.append({
                    "start": round(chunk_start, 3),
                    "end": round(chunk_end, 3),
                    "text": chunk,
                    "style": _choose_caption_style(chunk),
                })

    if not cues:
        return False

    mode = (settings.CAPTION_STYLE_MODE or "hybrid").strip().lower()
    ai_limit = max(0, settings.CAPTION_STYLE_AI_MAX_CUES)
    if mode in {"ai", "hybrid"} and ai_limit > 0:
        ai_indexes = [
            idx for idx, cue in enumerate(cues)
            if mode == "ai" or cue.get("style") == "neutral"
        ][:ai_limit]
        ai_texts = [cues[idx]["text"] for idx in ai_indexes]
        ai_styles = _infer_caption_styles_with_ai(ai_texts)
        if ai_styles:
            for idx, style in zip(ai_indexes, ai_styles):
                if style in STYLE_IDS:
                    cues[idx]["style"] = style
            if thought_callback:
                thought_callback(process_id, f"Caption Engine: AI style pass applied on clip {clip_index} ({len(ai_styles)} cues, mode={mode}, model={_choose_style_model()}).")

    _diversify_style_sequence(cues, settings.CAPTION_STYLE_MIN_VARIETY)
    _assign_visual_variants(cues)
    if thought_callback and cues:
        unique_styles = len({c.get("style", "neutral") for c in cues})
        thought_callback(process_id, f"Caption Engine: Clip {clip_index} overlay styles diversified ({unique_styles} style groups).")

    payload = {
        "styles": CAPTION_STYLES,
        "cues": cues,
    }
    with open(cues_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return True

def cut_video(video_path: str, hooks: List[Dict], process_id: str = None, active_pids: dict = None, thought_callback=None, transcript: Optional[str] = None) -> List[str]:
    """Cuts a video into clips with PID tracking and live streaming."""
    output_clips = []
    raw_base_name = os.path.basename(video_path)
    clean_base_name = sanitize_filename(raw_base_name)
    clips_dir = os.path.join(settings.UPLOAD_DIR, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    video_duration = get_video_duration(video_path)
    min_len = settings.CLIP_MIN_SECONDS
    max_len = settings.CLIP_MAX_SECONDS
    padding = settings.CLIP_PADDING_SECONDS
    transcript_segments = _parse_transcript_segments(transcript)
    can_burn_subtitles = _ffmpeg_supports_filter("subtitles")

    for i, hook in enumerate(hooks):

        start = _safe_float(hook.get('start', 0.0), 0.0)
        end = _safe_float(hook.get('end', 0.0), 0.0)
        if end < start:
            start, end = end, start

        # Add context padding.
        start = max(0.0, start - padding)
        end = end + padding

        # Enforce minimum length.
        duration = end - start
        if duration < min_len:
            end = start + min_len
            duration = min_len

        # Enforce maximum length.
        if duration > max_len:
            midpoint = (start + end) / 2
            start = midpoint - (max_len / 2)
            end = midpoint + (max_len / 2)

        # Clamp to media duration.
        if video_duration > 0:
            start = max(0.0, min(start, video_duration))
            end = max(0.0, min(end, video_duration))

            # Re-enforce min length after clamp if possible.
            duration = end - start
            if duration < min_len:
                if start + min_len <= video_duration:
                    end = start + min_len
                elif end - min_len >= 0:
                    start = end - min_len

        duration = end - start
        if duration <= 0:
            continue
            
        output_name = f"{clean_base_name}_hook_{i+1}.mp4"
        output_path = os.path.join(clips_dir, output_name)
        subtitle_ext = "ass" if settings.CLIP_ENABLE_ANIMATED_CAPTIONS else "srt"
        subtitle_path = os.path.join(clips_dir, f"{clean_base_name}_hook_{i+1}.{subtitle_ext}")
        subtitle_vtt_path = os.path.join(clips_dir, f"{clean_base_name}_hook_{i+1}.vtt")
        subtitle_cues_path = os.path.join(clips_dir, f"{clean_base_name}_hook_{i+1}.cues.json")
        
        if thought_callback:
            thought_callback(process_id, f"FFmpeg: Surgically extracting clip {i+1} ({start:.2f}s to {end:.2f}s | {duration:.2f}s)...")
        
        try:
            if settings.CLIP_ENABLE_SUBTITLES and transcript_segments:
                _write_clip_vtt(
                    subtitle_vtt_path,
                    transcript_segments,
                    clip_start=start,
                    clip_end=end,
                    max_words=max(3, settings.CLIP_SUBTITLE_MAX_WORDS),
                )
                _write_clip_cues_json(
                    subtitle_cues_path,
                    transcript_segments,
                    clip_start=start,
                    clip_end=end,
                    max_words=max(3, settings.CLIP_SUBTITLE_MAX_WORDS),
                    process_id=process_id,
                    thought_callback=thought_callback,
                    clip_index=i + 1,
                )
                if thought_callback and not can_burn_subtitles:
                    thought_callback(process_id, f"Caption Engine: ffmpeg lacks 'subtitles' filter; using soft subtitle track fallback for clip {i+1}.")

            attempts = [
                {"enable_format": True, "enable_transitions": True, "enable_zoom": True, "enable_subtitles": can_burn_subtitles, "animated_captions": True},
                {"enable_format": True, "enable_transitions": True, "enable_zoom": True, "enable_subtitles": can_burn_subtitles, "animated_captions": False},
                {"enable_format": True, "enable_transitions": True, "enable_zoom": True, "enable_subtitles": False, "animated_captions": False},
                {"enable_format": False, "enable_transitions": False, "enable_zoom": False, "enable_subtitles": False, "animated_captions": False},
            ]

            success = False
            last_output = ""
            for attempt_index, attempt in enumerate(attempts, start=1):
                if thought_callback and attempt_index > 1:
                    thought_callback(process_id, f"FFmpeg fallback {attempt_index}: simplifying render filters for clip {i+1}.")

                cmd = _build_ffmpeg_command(
                    video_path=video_path,
                    start=start,
                    duration=duration,
                    output_path=output_path,
                    subtitle_path=subtitle_path,
                    transcript_segments=transcript_segments,
                    process_id=process_id,
                    thought_callback=thought_callback,
                    clip_index=i + 1,
                    enable_format=attempt["enable_format"],
                    enable_transitions=attempt["enable_transitions"],
                    enable_zoom=attempt["enable_zoom"],
                    enable_subtitles=attempt["enable_subtitles"],
                    animated_captions=attempt["animated_captions"],
                )

                success, last_output = _run_ffmpeg_command(cmd, process_id=process_id, active_pids=active_pids)
                if success:
                    output_clips.append(output_name)
                    break

            if not success:
                print(f"Error cutting clip {i+1}: ffmpeg failed after retries. Output:\n{last_output}")
        except Exception as e:
            print(f"Error cutting clip {i+1}: {str(e)}")
            
    return output_clips
