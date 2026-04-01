import os
import subprocess
import re
from typing import List, Dict
from .config import settings

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

def cut_video(video_path: str, hooks: List[Dict], process_id: str = None, active_pids: dict = None, thought_callback=None) -> List[str]:
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
        
        if thought_callback:
            thought_callback(process_id, f"FFmpeg: Surgically extracting clip {i+1} ({start:.2f}s to {end:.2f}s | {duration:.2f}s)...")
        
        try:
            cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", video_path, "-t", str(duration)]

            if settings.CLIP_ENABLE_TRANSITIONS:
                fade_len = max(0.05, min(settings.CLIP_FADE_SECONDS, max(0.05, duration / 3)))
                fade_out_start = max(0.0, duration - fade_len)
                vf_parts = [
                    f"fade=t=in:st=0:d={fade_len}",
                    f"fade=t=out:st={fade_out_start}:d={fade_len}",
                ]
                af_parts = [
                    f"afade=t=in:st=0:d={fade_len}",
                    f"afade=t=out:st={fade_out_start}:d={fade_len}",
                ]

                if settings.CLIP_ENABLE_SUBTLE_ZOOM:
                    zoom_max = max(1.0, settings.CLIP_ZOOM_MAX)
                    vf_parts.append(
                        f"scale=iw*{zoom_max}:ih*{zoom_max},crop=iw/{zoom_max}:ih/{zoom_max}"
                    )

                cmd.extend(["-vf", ",".join(vf_parts), "-af", ",".join(af_parts)])

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
