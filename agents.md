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
- **Goal:** To extract high-impact insights from transcripts and generate engaging social media copy.
- **System Prompt Identity:** A viral content strategist who identifies "hooks" with timestamps and writes compelling captions.
- **Focus Areas:** 
    - Viral Hook Identification (First 3 seconds).
    - Engagement-driven Captioning.
    - Contextual understanding of UGC style.

## 3. Workflow Manager (The Orchestrator)
- **Role:** FastAPI Backend logic.
- **Goal:** Managing the lifecycle of a video processing request, ensuring that the Perception Agent passes its output to the Strategist Agent and that errors are gracefully handled.
