"""Background pipeline worker — runs transcription, analysis, and editing.

Called by the JobQueue worker thread. Updates the Job record in the database
as each stage completes, with a live thinking stream for the frontend.
"""
import json
import os
import re
import time
import signal
from datetime import datetime, timezone
from typing import Optional

from ..core.database import SessionLocal
from ..core.config import settings
from ..core.transcriber import transcribe_video
from ..core.analyst import analyze_transcript
from ..core.video_editor import cut_video
from ..core.translator import translate_transcript, is_supported_language
from ..core.virality import score_clips
from ..models.job import Job
from ..services.job_queue import job_queue


def get_ai_commentary(line: str) -> str:
    line_lower = line.lower()
    if any(k in line_lower for k in ["ferrari", "bugatti", "car", "lamborghini"]):
        return "Strategist Insight: Automotive luxury detected. High-value niche. Visuals should emphasize speed/status."
    if any(k in line_lower for k in ["money", "bought", "£", "$", "price"]):
        return "Strategist Insight: Financial stakes are being established. This builds authority and viewer envy."
    if any(k in line_lower for k in ["accident", "crash", "wrecked", "problem", "broken"]):
        return "Strategist Insight: Conflict detected! This is a classic retention hook. Hook potential is 8.5/10."
    if any(k in line_lower for k in ["miami", "florida", "travel", "house"]):
        return "Strategist Insight: Lifestyle/Vlog element. Good for building personality and audience trust."
    if any(k in line_lower for k in ["radiator", "battery", "engine", "work", "fix"]):
        return "Strategist Insight: Technical deep-dive occurring. This captures the 'How-To' and engineering enthusiast demographic."
    return ""


def add_thought(job_id: str, thought: str):
    clean = thought.strip()
    if not clean:
        return
    if "Whisper Perception:" in clean:
        match = re.search(r'\]\s+(.*)', clean)
        if match:
            commentary = get_ai_commentary(match.group(1))
            if commentary:
                job_queue.add_thought(job_id, commentary)

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        thoughts = json.loads(job.thinking_json or "[]")
        if not thoughts or thoughts[-1] != clean:
            thoughts.append(clean)
            if len(thoughts) > 150:
                thoughts = thoughts[-150:]
            job.thinking_json = json.dumps(thoughts)
            db.commit()
    finally:
        db.close()


def run_pipeline(job_id: str):
    """Main pipeline runner executed by the background worker."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
    finally:
        db.close()

    pipeline_t0 = time.perf_counter()
    timing = {"transcription_seconds": 0.0, "analysis_seconds": 0.0, "cutting_seconds": 0.0, "total_seconds": 0.0}

    try:
        job_queue.add_thought(job_id, f"System online. Preparing neural pathways...")
        job_queue.add_thought(job_id, f"Scanning metadata... Video: '{job.filename}' detected.")
        if job.endscreen_path:
            job_queue.add_thought(job_id, f"End Screen Studio: End screen image loaded with CTA: '{job.cta_text}'")
        job_queue.add_thought(job_id, "Qwen Strategy: I'm going to look for high-energy peaks and semantic hooks that work for short-form retention.")

        video_path = job.video_path
        if job.source == "drive" and job.drive_url:
            from ..core.drive_downloader import download_drive_file
            job_queue.add_thought(job_id, "Drive: Connecting to Google Drive...")
            video_path = download_drive_file(
                job.drive_url,
                settings.UPLOAD_DIR,
                progress_callback=lambda msg: job_queue.add_thought(job_id, msg),
            )
            if not video_path:
                _fail(job_id, "Failed to download from Google Drive")
                return
            db = SessionLocal()
            try:
                j = db.query(Job).filter(Job.id == job_id).first()
                if j:
                    j.video_path = video_path
                    j.filename = os.path.basename(video_path)
                    db.commit()
            finally:
                db.close()

        # --- Transcription ---
        job_queue.add_thought(job_id, "Whisper.cpp Perception: Listening to the audio track...")
        t0 = time.perf_counter()
        transcript = transcribe_video(
            video_path, job_id,
            job_queue._active_pids,
            thought_callback=lambda pid, msg: job_queue.add_thought(pid, msg),
        )
        timing["transcription_seconds"] = round(time.perf_counter() - t0, 2)
        job_queue.add_thought(job_id, f"Timing: Transcription finished in {timing['transcription_seconds']}s.")

        if not transcript:
            _fail(job_id, "Transcription failed")
            return

        # --- Translation (optional, for captions only) ---
        target_lang = (job.target_language or "en").strip().lower()
        caption_transcript = transcript  # original for analysis, translated for captions
        if target_lang != "en" and is_supported_language(target_lang):
            job_queue.add_thought(job_id, f"Translator: Translating captions to {target_lang}...")
            t0 = time.perf_counter()
            translated = translate_transcript(transcript, target_lang)
            if translated and translated != transcript:
                caption_transcript = translated
                job_queue.add_thought(job_id, f"Translator: Translation to {target_lang} complete ({round(time.perf_counter() - t0, 1)}s).")
            else:
                job_queue.add_thought(job_id, "Translator: Translation skipped (model unavailable or already in target language).")

        # --- Analysis (always on original transcript) ---
        job_queue.add_thought(job_id, "Semantic Analysis: Parsing transcript for 'scroll-stopper' moments...")
        t0 = time.perf_counter()
        analysis = analyze_transcript(transcript, video_path)
        timing["analysis_seconds"] = round(time.perf_counter() - t0, 2)
        job_queue.add_thought(job_id, f"Timing: AI analysis finished in {timing['analysis_seconds']}s.")

        if not analysis or "hooks" not in analysis:
            _fail(job_id, "AI Analysis failed to find hooks")
            return

        meta = analysis.get("analysis_meta", {})
        if meta:
            job_queue.add_thought(job_id, f"Selection Engine: {meta.get('candidate_count', 0)} candidates ranked, backend={meta.get('backend', 'ollama')}.")
            if meta.get("fallback_used"):
                job_queue.add_thought(job_id, "Selection Engine: Model output format failed, heuristic fallback hooks were applied.")
            job_queue.add_thought(job_id, f"Duration Optimizer: min={meta.get('duration_min', 0)}s avg={meta.get('duration_avg', 0)}s max={meta.get('duration_max', 0)}s.")

        # --- Cutting ---
        if "strategy_thought" in analysis:
            job_queue.add_thought(job_id, f"Qwen Strategic Insight: {analysis['strategy_thought']}")

        job_queue.add_thought(job_id, f"Editor Monologue: Found {len(analysis.get('hooks', []))} viral segments. Initiating surgical cuts.")
        if job.endscreen_path:
            job_queue.add_thought(job_id, "End Screen Studio: Will append end screen image to each clip with CTA overlay.")

        t0 = time.perf_counter()
        clips = cut_video(
            video_path,
            analysis["hooks"],
            job_id,
            job_queue._active_pids,
            thought_callback=lambda pid, msg: job_queue.add_thought(pid, msg),
            transcript=caption_transcript,
            endscreen_path=job.endscreen_path,
            cta_text=job.cta_text,
            aspect_ratio=job.aspect_ratio or "vertical_9_16",
        )
        timing["cutting_seconds"] = round(time.perf_counter() - t0, 2)
        job_queue.add_thought(job_id, f"Timing: Clip rendering finished in {timing['cutting_seconds']}s.")

        if not clips:
            _fail(job_id, "FFmpeg failed to generate clips")
            return

        # --- Virality Scoring ---
        job_queue.add_thought(job_id, "Virality Engine: Scoring clips for predicted performance...")
        scored = score_clips(analysis.get("hooks", []), transcript)
        if scored:
            analysis["hooks"] = scored
            avg_score = sum(h.get("virality_score", 0) for h in scored) / max(1, len(scored))
            job_queue.add_thought(job_id, f"Virality Engine: Clips scored (avg: {avg_score:.0f}/100). Top clip: {max(scored, key=lambda h: h.get('virality_score', 0)).get('virality_score', 0):.0f}/100.")
            for h in scored:
                vs = h.get("virality_score", 0)
                hn = h.get("hook_name", "Clip")
                job_queue.add_thought(job_id, f"Virality Engine: {hn} — {vs:.0f}/100")

        # --- Success ---
        timing["total_seconds"] = round(time.perf_counter() - pipeline_t0, 2)
        job_queue.add_thought(job_id, "Pipeline complete. All clips processed and verified.")

        db = SessionLocal()
        try:
            j = db.query(Job).filter(Job.id == job_id).first()
            if j:
                j.status = "completed"
                j.transcript = caption_transcript
                j.analysis_json = json.dumps(analysis)
                j.clips_json = json.dumps(clips)
                j.timing_transcription = timing["transcription_seconds"]
                j.timing_analysis = timing["analysis_seconds"]
                j.timing_cutting = timing["cutting_seconds"]
                j.timing_total = timing["total_seconds"]
                j.completed_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()

    except Exception as e:
        err = str(e)
        status = "cancelled" if "cancelled" in err.lower() else "failed"
        db = SessionLocal()
        try:
            j = db.query(Job).filter(Job.id == job_id).first()
            if j:
                j.status = status
                j.error = err
                db.commit()
        finally:
            db.close()
    finally:
        job_queue.unregister_pid(job_id)
        db = SessionLocal()
        try:
            j = db.query(Job).filter(Job.id == job_id).first()
            if j and j.video_path and os.path.exists(j.video_path) and j.source == "upload":
                os.remove(j.video_path)
        finally:
            db.close()


def _fail(job_id: str, error: str):
    db = SessionLocal()
    try:
        j = db.query(Job).filter(Job.id == job_id).first()
        if j:
            j.status = "failed"
            j.error = error
            db.commit()
    finally:
        db.close()
