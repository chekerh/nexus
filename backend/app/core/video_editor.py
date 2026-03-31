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

def cut_video(video_path: str, hooks: List[Dict], process_id: str = None, active_pids: dict = None) -> List[str]:
    """Cuts a video into multiple clips based on start/end timestamps using FFmpeg with PID tracking."""
    output_clips = []
    
    # Sanitize the base name for the output files
    raw_base_name = os.path.basename(video_path)
    clean_base_name = sanitize_filename(raw_base_name)
    
    # Ensure clips directory exists
    clips_dir = os.path.join(settings.UPLOAD_DIR, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    for i, hook in enumerate(hooks):
        # Check if cancelled before each clip
        if active_pids is not None and process_id not in active_pids and process_id is not None:
             # This means the PID was removed, likely due to cancellation
             break

        start = hook.get('start', 0)
        end = hook.get('end', 0)
        
        # Calculate duration
        duration = end - start
        if duration <= 0:
            print(f"Skipping hook {i+1}: Invalid duration ({duration}s)")
            continue
            
        output_name = f"{clean_base_name}_hook_{i+1}.mp4"
        output_path = os.path.join(clips_dir, output_name)
        
        try:
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", video_path,
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                output_path
            ]
            
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if process_id and active_pids is not None:
                active_pids[process_id] = process.pid
                
            process.communicate()
            
            if process.returncode == 0:
                output_clips.append(output_name)
                print(f"Generated accurate clip: {output_name}")
            
        except Exception as e:
            print(f"Error cutting clip {i+1}: {str(e)}")
            
    return output_clips
