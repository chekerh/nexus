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
- **Role:** Acts as the "Creative Director." It parses transcripts with timestamps to identify high-retention segments and generates viral strategies.
- **Phase 3 Enhancement:** Now provides "thinking streams" to the UI to show the reasoning process.

### Video Editing Engine (FFmpeg)
- **Role:** Performs precise, frame-accurate re-encoding of video segments based on AI-determined timestamps.

## 3. Storage
- **Local Data (`backend/data/`):** Temporary storage for uploads.
- **Clips Library (`backend/data/clips/`):** Permanent (per session) storage for generated viral reels.

## 4. Interaction Model (Phase 3)
- **Real-time Feedback:** Instead of static loaders, the system now provides a "Thinking Console" showing the AI's step-by-step logic.
- **User Control:** Added "Stop Analysis" capability to immediately terminate resource-heavy AI or FFmpeg processes.
