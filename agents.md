# Nexus-UGC: Agent Definitions (Current)

## 1) Perception Agent
- **Runtime:** Whisper.cpp
- **Purpose:** timestamped transcript extraction from raw video audio.
- **Behavior:** filter out non-content runtime logs before downstream analysis.

## 2) Strategist Agent
- **Runtime:** Qwen via Ollama
- **Purpose:** select high-retention windows + captions + confidence.
- **Inputs:**
	- strategist playbook prompt file
	- viral signals rubric
	- hybrid-ranked candidate windows
- **Output policy:** produce 3 hooks with adaptive durations, not uniform clip lengths.

## 3) Scoring Agent (Heuristic Layer)
- **Purpose:** pre-rank candidate windows for strategist grounding.
- **Signals:** semantic keywords, speech density, optional scene boundaries, duration diversity.

## 4) Caption Style Agent (Heuristic Style Selector)
- **Purpose:** select phrase-level subtitle style classes.
- **Styles:** neutral, impact, question, money, warning, hype.
- **Artifacts:** cue JSON sidecar consumed by frontend overlay renderer.

## 5) Editing Agent
- **Runtime:** FFmpeg pipeline with fallbacks.
- **Purpose:** render robust outputs even if advanced filters are unavailable.
- **Modes:** full effects -> simplified effects -> minimal baseline.

## 6) Publishing Agent
- **Purpose:** route clips to selected account/platform.
- **Modes:**
	- direct API publish when credentials are valid
	- safe manual fallback when not

## 7) Orchestrator Agent
- **Purpose:** lifecycle control, progress stream, cancellation, result aggregation.
