import os
import subprocess
import re
from typing import List, Dict, Optional
from .config import settings

TRANSCRIPT_LINE_RE = re.compile(r'^\[(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3})\]\s+(.*)$')

SUBTITLE_PRESETS = {
    "bold_center": "Alignment=2,FontName=Arial,FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H80000000,Bold=1,Outline=2,Shadow=0,MarginV=28",
    "tiktok_pop": "Alignment=2,FontName=Arial,FontSize=18,PrimaryColour=&H0000F9FF,OutlineColour=&H00000000,BackColour=&H80000000,Bold=1,Outline=3,Shadow=0,MarginV=34",
    "clean_minimal": "Alignment=2,FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H50000000,Bold=0,Outline=1,Shadow=0,MarginV=24",
}

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
        subtitle_path = os.path.join(clips_dir, f"{clean_base_name}_hook_{i+1}.srt")
        
        if thought_callback:
            thought_callback(process_id, f"FFmpeg: Surgically extracting clip {i+1} ({start:.2f}s to {end:.2f}s | {duration:.2f}s)...")
        
        try:
            cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", video_path, "-t", str(duration)]
            vf_parts = []
            af_parts = []

            if settings.CLIP_ENABLE_TRANSITIONS:
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

                if settings.CLIP_ENABLE_SUBTLE_ZOOM:
                    zoom_max = max(1.0, settings.CLIP_ZOOM_MAX)
                    vf_parts.append(
                        f"scale=iw*{zoom_max}:ih*{zoom_max},crop=iw/{zoom_max}:ih/{zoom_max}"
                    )

            if settings.CLIP_ENABLE_SUBTITLES and transcript_segments:
                if _write_clip_srt(
                    subtitle_path,
                    transcript_segments,
                    clip_start=start,
                    clip_end=end,
                    max_words=max(3, settings.CLIP_SUBTITLE_MAX_WORDS),
                ):
                    preset = SUBTITLE_PRESETS.get(settings.CLIP_SUBTITLE_PRESET, SUBTITLE_PRESETS["bold_center"])
                    escaped_sub_path = _escape_filter_path(subtitle_path)
                    vf_parts.append(f"subtitles='{escaped_sub_path}':force_style='{preset}'")
                    if thought_callback:
                        thought_callback(process_id, f"Caption Engine: Burn-in subtitles enabled for clip {i+1} ({settings.CLIP_SUBTITLE_PRESET}).")

            if vf_parts:
                cmd.extend(["-vf", ",".join(vf_parts)])
            if af_parts:
                cmd.extend(["-af", ",".join(af_parts)])

            cmd.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", output_path])
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                preexec_fn=os.setsid
            )
            
            if process_id and active_pids is not None:
                active_pids[process_id] = process.pid
                
            # Read output if needed for progress
            for line in process.stdout:
                pass
                
            process.wait()
            if process.returncode == 0:
                output_clips.append(output_name)
        except Exception as e:
            print(f"Error cutting clip {i+1}: {str(e)}")
            
    return output_clips
