import os
import subprocess
import ffmpeg
from typing import Optional
from .config import settings

def extract_audio(video_path: str, audio_output_path: str) -> bool:
    """Extracts 16kHz mono WAV from video using ffmpeg for Whisper compatibility."""
    try:
        (
            ffmpeg
            .input(video_path)
            .output(audio_output_path, acodec='pcm_s16le', ac=1, ar='16k')
            .overwrite_output()
            .run(quiet=True)
        )
        return True
    except ffmpeg.Error as e:
        print(f"Error extracting audio: {e.stderr.decode() if e.stderr else str(e)}")
        return False

def transcribe_video(video_path: str, process_id: str = None, active_pids: dict = None) -> Optional[str]:
    """Converts video audio to text using a local whisper.cpp binary with PID tracking."""
    base_name = os.path.basename(video_path)
    audio_path = os.path.join(settings.UPLOAD_DIR, f"{base_name}.wav")
    
    if not extract_audio(video_path, audio_path):
        return None

    try:
        # -np: no prints (results only), timestamps enabled by default
        cmd = [settings.WHISPER_BINARY_PATH, "-m", settings.WHISPER_MODEL_PATH, "-f", audio_path, "-np"]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Register PID
        if process_id and active_pids is not None:
            active_pids[process_id] = process.pid
            
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"Whisper transcription failed: {stderr}")
            return None
            
        if os.path.exists(audio_path):
            os.remove(audio_path)
            
        return stdout.strip()
    except Exception as e:
        print(f"Error during transcription: {str(e)}")
        return None
    finally:
        if process_id and active_pids is not None:
            active_pids.pop(process_id, None)
