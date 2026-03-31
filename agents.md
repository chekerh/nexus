# PubReelo: AI Agents Definition

This document defines the specialized AI entities that form the PubReelo Intelligence Layer.

## 1. Perception Agent (The Transcriber)
- **Model:** Whisper.cpp (OpenAI Whisper GGML)
- **Role:** High-fidelity audio perception.
- **Goal:** To convert raw audio into a clean, accurate text transcript.
- **Constraints:** Optimized for speed and low CPU overhead on local machines. Handles various accents and audio quality levels.

## 2. Strategist Agent (The Analyst)
- **Model:** Qwen3:30b (Ollama)
- **Role:** Viral content strategist and creative director.
- **Goal:** Identify 3 high-impact hooks and provide exact start/end timestamps for cutting.
- **Focus Areas:** 
    - Viral Hook Identification (First 3 seconds).
    - Engagement-driven Captioning.
    - **Temporal Precision:** Accurate identification of video timestamps from transcript context.

## 3. Workflow Manager (The Orchestrator)
- **Role:** FastAPI Backend logic & Video Editor.
- **Goal:** Manage the lifecycle of a request, including the invocation of FFmpeg for Phase 2 video cutting.
- **New Task:** Perform lossless video extraction based on the Strategist's timestamps.
