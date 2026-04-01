# Nexus-UGC: Data Flow Pipeline (Current)

## 1) Upload & job creation
- User uploads video in dashboard.
- Backend writes file under `backend/data/` and creates `process_id` state.

## 2) Perception: audio + transcript
- FFmpeg extracts 16k mono WAV.
- Whisper.cpp transcribes with timestamps.
- Internal runtime noise lines are filtered before analysis.

## 3) Hybrid strategy analysis
- Transcript is parsed into timestamp segments.
- Candidate windows are ranked using:
	- semantic cues
	- speech density
	- optional scene-cut evidence (configurable)
	- adaptive duration heuristics (non-uniform lengths)
- Qwen receives:
	- strategist playbook
	- viral rubric
	- candidate summary + transcript
- Output: hooks (`start/end/caption/confidence`).

## 4) Editing and enhancement
- Clip windows are padded + clamped to valid media bounds.
- FFmpeg renders each clip with selected profile:
	- format preset (`9:16`, etc.)
	- transitions
	- subtle zoom
	- subtitles (burn-in when available)
- If burn-in is unavailable or fails:
	- generate `.vtt` soft subtitles
	- generate `.cues.json` for styled overlay in frontend
	- retry with simplified filter stack (fallback ladder).

## 5) Delivery
- Backend returns transcript, hooks, and clip file names.
- Frontend renders clip players, subtitle tracks, and styled subtitle overlays.

## 6) Publishing pipeline
- User picks destination account per clip.
- Backend attempts direct publish per platform when credentials are present:
	- YouTube OAuth upload
	- Instagram Graph Reels flow
	- TikTok Open API init flow
- Otherwise, safe manual upload fallback URL is returned.

## 7) State + persistence
- Account store: `backend/data/accounts.json`
- Publish history: `backend/data/publish_history.json`
- Clips + subtitle artifacts: `backend/data/clips/`
