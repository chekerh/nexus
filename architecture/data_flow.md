# PubReelo: Data Flow Pipeline

The PubReelo system follows a strictly local, sequential pipeline for processing video content.

## 1. Upload & Ingestion
- User uploads an `.mp4` or `.mov` file through the Dashboard.
- FastAPI backend saves the file to `backend/data/{uuid}_filename.ext`.
- An entry is created in the in-memory `processing_results` store with status `processing`.

## 2. Audio Extraction (FFmpeg)
- The system extracts audio from the video file.
- **Format:** `WAV` (PCM 16-bit, Mono, 16,000 Hz).
- The extracted WAV file is temporarily saved in `backend/data/`.

## 3. Transcription (Perception Layer)
- `whisper-cli` is called as a subprocess, passing the temporary WAV file and the local `ggml` model.
- **Output:** A raw text transcript (timestamps suppressed with `-nt`).
- Status is updated to "Extracting audio and transcribing...".

## 4. Viral Analysis (Intelligence Layer)
- The raw transcript is sent to the local **Ollama** server via a Chat API call.
- **Model:** `qwen3:30b`.
- **System Prompt:** Instructs the model to act as a viral strategist, identifying 3 hooks and writing captions.
- Status is updated to "Analyzing transcript for viral hooks (Ollama)...".

## 5. Result Delivery & Cleanup
- The final transcript and AI analysis are stored in the `processing_results` map.
- Status is updated to `completed`.
- Temporary video and audio files are deleted from `backend/data/`.
- The Frontend polls the `/status/{id}` endpoint, detects completion, and renders the content.
