# Nexus-UGC: Agent Definitions & Coding Standards

## Agent Architecture

### 1) Perception Agent
- **Runtime:** Whisper.cpp
- **Purpose:** timestamped transcript extraction from raw video audio.
- **Behavior:** filter out non-content runtime logs before downstream analysis.

### 2) Strategist Agent
- **Runtime:** Qwen via Ollama
- **Purpose:** select high-retention windows + captions + confidence.
- **Inputs:**
  - strategist playbook prompt file
  - viral signals rubric
  - hybrid-ranked candidate windows
- **Output policy:** produce 3 hooks with adaptive durations, not uniform clip lengths.

### 3) Scoring Agent (Heuristic Layer)
- **Purpose:** pre-rank candidate windows for strategist grounding.
- **Signals:** semantic keywords, speech density, optional scene boundaries, duration diversity.

### 4) Caption Style Agent (Heuristic Style Selector)
- **Purpose:** select phrase-level subtitle style classes.
- **Styles:** neutral, impact, question, money, warning, hype.
- **Artifacts:** cue JSON sidecar consumed by frontend overlay renderer.

### 5) Editing Agent
- **Runtime:** FFmpeg pipeline with fallbacks.
- **Purpose:** render robust outputs even if advanced filters are unavailable.
- **Modes:** full effects -> simplified effects -> minimal baseline.
- **Critical Rules:**
  - Always calculate exact pixel dimensions in Python, never use FFmpeg expressions for crop/scale
  - Test filter chains with actual FFmpeg version before deploying
  - Captions must be burned during initial cut, not appended later
  - End screen dimensions must match video exactly before concat

### 6) Publishing Agent
- **Purpose:** route clips to selected account/platform.
- **Modes:**
  - direct API publish when credentials are valid
  - safe manual fallback when not

### 7) Orchestrator Agent
- **Purpose:** lifecycle control, progress stream, cancellation, result aggregation.

---

## Coding Standards & Best Practices

### FFmpeg Filter Guidelines
1. **Never use complex expressions** in FFmpeg filters for FFmpeg 8.0+ (e.g., `if(gt(a,1.78),...)`)
2. **Always pre-calculate dimensions** in Python, pass exact integers to filters
3. **Scale → Crop workflow:**
   - Calculate target scale to cover frame (scale up, never down for crop-to-fill)
   - Calculate exact crop coordinates from scaled dimensions
   - Use simple filter chain: `scale=w:h,crop=w:h:x:y`
4. **Text escaping for drawtext:**
   - Single quote `'` → `\\'`
   - Colon `:` → `\\:`
   - Comma in enable expressions: `between(t\\,start\\,end)`

### Error Handling
1. Use try/except with specific exceptions
2. Log errors with context (file paths, dimensions, filter strings)
3. Always clean up temp files in finally blocks
4. Provide graceful fallbacks for all features

### Performance
1. Use hardware encoders when available (h264_videotoolbox)
2. Fall back to software (libx264) with ultrafast preset
3. Minimize filter chain complexity
4. Batch operations where possible

### Testing Checklist for Video Features
- [ ] Test with 16:9 landscape source video
- [ ] Test with 9:16 portrait source video
- [ ] Test with square source video
- [ ] Test end screen with landscape image
- [ ] Test end screen with portrait image
- [ ] Test captions with special characters (quotes, colons, unicode)
- [ ] Verify downloaded video has burned captions
- [ ] Verify CTA appears at correct timestamp
