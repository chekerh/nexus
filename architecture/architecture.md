# PubReelo: System Architecture

## 1. Overview
PubReelo is a local-first AI pipeline designed to automate the creation of viral social media content (hooks, captions, and strategy) from raw UGC (User Generated Content) videos.

## 2. Core Components

### Frontend (UGC Dashboard)
- **Tech Stack:** Vanilla HTML5, CSS3, JavaScript.
- **Role:** Handles video file selection, triggers the processing pipeline via REST API, and displays real-time status and final results (transcripts and AI-generated hooks).

### Backend (FastAPI Strategy Engine)
- **Tech Stack:** Python 3.14+, FastAPI, Uvicorn.
- **Role:** Orchestrates the pipeline. It handles file uploads, manages background tasks for heavy processing, and provides status polling for the frontend.

### Perception Layer (Whisper.cpp)
- **Model:** `ggml-base.en.bin` (running locally).
- **Role:** Converts audio from video files into clean text transcripts. It is optimized for local CPU/GPU performance.

### Intelligence Layer (Ollama / Qwen)
- **Model:** `qwen3:30b` (running via local Ollama instance).
- **Role:** Analyzes raw transcripts to identify viral "hooks" and generate high-engagement social media captions.

## 3. Storage
- **Local Data (`backend/data/`):** Temporary storage for uploaded video files and extracted audio chunks. Files are cleaned up after processing to save disk space.

## 4. Integration
- **FFmpeg:** Used for pre-processing videos and extracting 16kHz mono audio required for Whisper.cpp.
- **REST API:** Standard interface for communication between the Frontend and the Backend.
