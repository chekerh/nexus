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

## 5. Automated Video Cutting (Phase 2)
- The backend parses the JSON output from the Strategist Agent to extract 3 sets of timestamps.
- **FFmpeg** is invoked for each hook to perform a "lossless cut" (using stream copying).
- **Command:** `ffmpeg -ss {start} -to {end} -i {input} -c copy {output}`.
- Three new video files are generated and stored in a public `clips/` directory.

## 6. Result Delivery & Cleanup
- The final transcript, AI analysis, and links to the 3 video clips are stored in the results.
- Status is updated to `completed`.
- Temporary raw audio and original upload files are managed/cleaned up.
- The Frontend renders the 3 video players for immediate preview.
