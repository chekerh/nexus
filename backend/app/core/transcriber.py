import logging
import os
import re
import subprocess

import ffmpeg

logger = logging.getLogger(__name__)

from .config import settings

TIMESTAMPED_LINE_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}\]\s+.+$")


def _is_noise_line(line: str) -> bool:
    lowered = line.lower()
    return lowered.startswith("whisper_print_timings:") or lowered.startswith("ggml_") or "deallocating" in lowered


def extract_audio(video_path: str, audio_output_path: str) -> bool:
    """Extracts 16kHz mono WAV from video using ffmpeg for Whisper compatibility."""
    try:
        (
            ffmpeg.input(video_path)
            .output(audio_output_path, acodec="pcm_s16le", ac=1, ar="16k")
            .overwrite_output()
            .run(quiet=True)
        )
        return True
    except ffmpeg.Error as e:
        logger.error(f"Error extracting audio: {e.stderr.decode() if e.stderr else str(e)}")
        return False


def transcribe_video(
    video_path: str, process_id: str | None = None, active_pids: dict | None = None, thought_callback=None
) -> str | None:
    """Converts video audio to text using a local whisper.cpp binary with PID tracking and live streaming."""
    base_name = os.path.basename(video_path)
    audio_path = os.path.join(settings.UPLOAD_DIR, f"{base_name}.wav")

    if thought_callback:
        thought_callback(process_id, "Whisper-Perception: Extracting 16kHz audio track...")

    if not extract_audio(video_path, audio_path):
        return None

    all_output = []
    try:
        cmd = [
            settings.WHISPER_BINARY_PATH,
            "-m",
            settings.WHISPER_MODEL_PATH,
            "-f",
            audio_path,
            "-t",
            str(max(1, settings.WHISPER_THREADS)),
            "-p",
            str(max(1, settings.WHISPER_PROCESSORS)),
        ]
        if settings.WHISPER_LANGUAGE:
            cmd.extend(["-l", settings.WHISPER_LANGUAGE])
        if settings.WHISPER_TRANSLATE:
            cmd.append("-tr")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            preexec_fn=os.setsid,  # Create a new process group
        )

        # Register PID
        if process_id and active_pids is not None:
            active_pids[process_id] = process.pid

        if process.stdout is None:
            raise RuntimeError("Whisper process did not expose an output stream")

        # Read output line by line as it happens
        for line in process.stdout:
            clean_line = line.strip()
            if clean_line:
                if _is_noise_line(clean_line):
                    continue

                if TIMESTAMPED_LINE_RE.match(clean_line):
                    all_output.append(clean_line)
                    if thought_callback:
                        thought_callback(process_id, f"Whisper Perception: {clean_line}")

        process.wait()

        if process.returncode != 0 and not (process_id and active_pids is not None and process_id not in active_pids):
            logger.error(f"Whisper transcription failed with code {process.returncode}")
            return None

        return "\n".join(all_output)
    except Exception as e:
        logger.error(f"Error during transcription: {e}")
        return None
    finally:
        if process_id and active_pids is not None:
            active_pids.pop(process_id, None)
        if os.path.exists(audio_path):
            os.remove(audio_path)
