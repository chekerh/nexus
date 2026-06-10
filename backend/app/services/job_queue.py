"""Database-backed job queue that survives restarts.

Replaces the in-memory processing_results dict with persistent storage.
A background worker thread polls for pending jobs and executes the pipeline.
"""
import json
import os
import signal
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Callable
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..models.job import Job
from ..core.config import settings


class JobQueue:
    """Thread-safe, DB-backed job queue with live thinking stream."""

    def __init__(self):
        self._active_pids: dict[str, int] = {}
        self._pipeline_runner = None
        self._lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False

    def set_pipeline_runner(self, runner: Callable):
        self._pipeline_runner = runner

    def start_worker(self):
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._worker_thread.start()

    def stop_worker(self):
        self._running = False

    def _poll_loop(self):
        while self._running:
            try:
                db = SessionLocal()
                try:
                    job = db.query(Job).filter(Job.status == "pending").order_by(Job.created_at).first()
                    if job and self._pipeline_runner:
                        with self._lock:
                            job.status = "running"
                            job.started_at = datetime.now(timezone.utc)
                            db.commit()
                        self._pipeline_runner(job.id)
                finally:
                    db.close()
            except Exception:
                pass
            time.sleep(2)

    def enqueue(self, db: Session, user_id: str, filename: str = "", video_path: str = "",
                endscreen_path: str = "", cta_text: str = "Link in bio to try it free.",
                source: str = "upload", drive_url: str = "", target_language: str = "en",
                aspect_ratio: str = "vertical_9_16") -> str:
        job = Job(
            user_id=user_id,
            filename=filename,
            video_path=video_path,
            endscreen_path=endscreen_path,
            cta_text=cta_text,
            source=source,
            drive_url=drive_url,
            target_language=target_language,
            aspect_ratio=aspect_ratio,
            status="pending",
            thinking_json="[]",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job.id

    def get_job(self, db: Session, job_id: str) -> Optional[Job]:
        return db.query(Job).filter(Job.id == job_id).first()

    def get_user_jobs(self, db: Session, user_id: str, limit: int = 50) -> list[Job]:
        return (db.query(Job).filter(Job.user_id == user_id)
                .order_by(Job.created_at.desc()).limit(limit).all())

    def cancel_job(self, db: Session, job_id: str) -> bool:
        job = self.get_job(db, job_id)
        if not job:
            return False
        job.status = "cancelled"
        db.commit()

        with self._lock:
            pid = self._active_pids.pop(job_id, None)
        if pid:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:
                pass
        return True

    def add_thought(self, job_id: str, thought: str):
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return
            thoughts = json.loads(job.thinking_json or "[]")
            thoughts.append(thought)
            if len(thoughts) > 150:
                thoughts = thoughts[-150:]
            job.thinking_json = json.dumps(thoughts)
            if job.status != "running":
                job.status = "running"
            db.commit()
        finally:
            db.close()

    def register_pid(self, job_id: str, pid: int):
        with self._lock:
            self._active_pids[job_id] = pid

    def unregister_pid(self, job_id: str):
        with self._lock:
            self._active_pids.pop(job_id, None)


job_queue = JobQueue()
