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

def cut_video(video_path: str, hooks: List[Dict], process_id: str = None, active_pids: dict = None, thought_callback=None) -> List[str]:
    """Cuts a video into clips with PID tracking and live streaming."""
    output_clips = []
    raw_base_name = os.path.basename(video_path)
    clean_base_name = sanitize_filename(raw_base_name)
    clips_dir = os.path.join(settings.UPLOAD_DIR, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    for i, hook in enumerate(hooks):

        start, end = hook.get('start', 0), hook.get('end', 0)
        duration = end - start
        if duration <= 0: continue
            
        output_name = f"{clean_base_name}_hook_{i+1}.mp4"
        output_path = os.path.join(clips_dir, output_name)
        
        if thought_callback:
            thought_callback(process_id, f"FFmpeg: Surgically extracting clip {i+1} ({start}s to {end}s)...")
        
        try:
            cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", video_path, "-t", str(duration), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", output_path]
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
