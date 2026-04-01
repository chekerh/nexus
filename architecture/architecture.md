# Nexus-UGC: System Architecture (Current)

## 1. Overview
Nexus-UGC is a local-first AI production system that:
1) analyzes long-form UGC,
2) finds viral candidate windows,
3) generates optimized short clips,
4) adds subtitle layers/styles,
5) routes clips to multi-account social publishing flows.

## 2. Core Components

### Frontend (Dashboard)
- **Tech:** Vanilla HTML/CSS/JS.
- **Capabilities:**
	- upload + run pipeline
	- live "thinking" stream
	- clips preview/download
	- subtitle overlay rendering from cue JSON
	- account management (TikTok/Instagram/YouTube)
	- publish action per selected account

### Backend (FastAPI Orchestrator)
- **Tech:** FastAPI + Uvicorn + Python services.
- **Capabilities:**
	- process lifecycle and cancellation
	- account CRUD + publish history
	- publish endpoints with platform connectors and safe fallback

### Perception Layer (Whisper.cpp)
- Extracts timestamped transcript lines from video audio.
- Noise filtering removes internal runtime logs before analysis.

### Intelligence Layer (Qwen via Ollama)
- Prompt-file driven strategist behavior (`prompts/`).
- Hybrid candidate scoring combines:
	- semantic viral cues,
	- speech density,
	- optional scene-boundary evidence,
	- duration diversity logic (non-uniform clip lengths).

### Editing Layer (FFmpeg)
- Dynamic clip window cutting with min/max constraints.
- Format presets (`vertical_9_16`, etc.).
- Transitions and subtle zoom.
- Subtitle pipeline:
	- animated/static caption generation,
	- soft-track fallback (`.vtt`) when burn-in filter unavailable,
	- style cues JSON for frontend overlay rendering.
- Multi-stage FFmpeg fallback to avoid total pipeline failure.

### Publishing Layer
- **YouTube:** direct upload (OAuth refresh token path).
- **Instagram Reels:** Graph API path (public media URL required).
- **TikTok:** Open API init path (token/app credentials required).
- **Fallback:** safe manual upload URLs when API prerequisites are missing.

## 3. Storage
- `backend/data/`:
	- temporary uploads/transcoding artifacts
	- `accounts.json`
	- `publish_history.json`
- `backend/data/clips/`:
	- generated `.mp4`
	- subtitle sidecars (`.vtt`, optional `.ass/.srt`)
	- style cue metadata (`.cues.json`)

## 4. Runtime Profiles & Optimization
- Configurable knobs in `.env`:
	- processing profile (`eco|balanced|quality`)
	- optional scene detection toggle
	- encoder selection (`auto`, videotoolbox, x264)
	- thread limits
	- subtitle style/animation parameters

## 5. Interaction Model
- Real-time thought stream across perception, analysis, and editing.
- Graceful degradation approach:
	- if advanced filters fail, progressively simplify rendering and still output clips.
