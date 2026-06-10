# Nexus-UGC v2: Data Flow

## Job Lifecycle

```
                   ┌──────────┐
                   │  PENDING │ ← API creates job record
                   └────┬─────┘
                        │ worker polls (every 2s)
                   ┌────▼─────┐
                   │  RUNNING │ ← transcription → analysis → editing
                   └────┬─────┘
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
        ┌────────┐ ┌────────┐ ┌────────┐
        │COMPLETE│ │FAILED  │ │CANCELLED│
        └────────┘ └────────┘ └────────┘
```

## Upload Flow (Authenticated)

1. User sends POST `/api/v1/process` with Bearer token + video file
2. Backend validates file, checks usage quota
3. Creates `Job` record in DB (status=`pending`)
4. Increments user's monthly credit usage
5. Returns `{process_id}` immediately
6. Worker thread picks up job, runs pipeline
7. Frontend polls `/api/v1/status/{id}` for live updates

## Transcription Flow

1. FFmpeg extracts 16kHz mono WAV from video
2. Whisper.cpp subprocess with PID tracking (for cancellation)
3. Live line-by-line output streamed to `thinking_json` in DB
4. Noise lines filtered out; timestamped lines preserved

## Analysis Flow

1. Transcript parsed into timestamped segments
2. Heuristic candidate scoring (keywords, speech density, scene cuts)
3. Top candidates sent to Qwen (Ollama/AirLLM) with strategist prompts
4. Structured JSON parsed for 3 hooks with start/end/caption/confidence
5. Fallback to heuristic-only hooks if LLM output is malformed

## Editing Flow

1. For each hook: pad, clamp to bounds, enforce min/max duration
2. FFmpeg renders clip with multi-stage fallback (full → simplified → minimal)
3. Caption pipeline: VTT (browser) + cues.json (styled overlay) + ASS/SRT (burn-in)
4. Optional: end screen image appended with CTA overlay
5. Artifacts written to `backend/data/clips/`

## Publishing Flow

1. User selects clip + target account
2. Backend decrypts account tokens
3. Attempts direct API publish (YouTube/Instagram/TikTok)
4. Falls back to manual upload URL if credentials missing
5. Publish history written to `publish_history.json`
