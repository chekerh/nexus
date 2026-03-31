# PubReelo: AI Agents Definition

This document defines the specialized AI entities that form the PubReelo Intelligence Layer.

## 1. Perception Agent (The Transcriber)
- **Model:** Whisper.cpp (OpenAI Whisper GGML)
- **Role:** High-fidelity audio perception.
- **Goal:** To convert raw audio into a clean, accurate text transcript.
- **Constraints:** Optimized for speed and low CPU overhead on local machines. Handles various accents and audio quality levels.

## 2. Strategist Agent (The Analyst)
- **Model:** Qwen3:30b (Ollama)
- **Role:** Creative Director & Content Strategist.
- **Goal:** Identify retention-driven segments and explain *why* they were chosen.
- **Expressiveness (Phase 3):** Now provides real-time "thinking logs" (e.g., "Evaluating comedic timing at 0:45", "Analyzing retention drop-off") to keep the user engaged.

## 3. Workflow Manager (The Orchestrator)
- **Role:** Controller & Editor.
- **Goal:** Manage execution lifecycle with cancellation support.
- **Interruptibility:** Can now handle "Stop Analysis" requests to kill background processes.
