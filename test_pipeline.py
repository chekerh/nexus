import os
import sys
import uuid
import shutil
from datetime import UTC, datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.core.database import SessionLocal, Base, engine
from app.models.user import User
from app.models.job import Job
from app.workers.pipeline import run_pipeline

def test():
    # Setup DB
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Ensure data dir exists
    os.makedirs("backend/data", exist_ok=True)
    
    # Create test user
    user = db.query(User).filter(User.email == "test@example.com").first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email="test@example.com",
            password_hash="test",
            created_at=datetime.now(UTC)
        )
        db.add(user)
        db.commit()

    # Create job
    job_id = str(uuid.uuid4())
    
    # Copy test video to data dir
    video_path = f"backend/data/{job_id}.mp4"
    shutil.copy("test_video.mp4", video_path)

    job = Job(
        id=job_id,
        user_id=user.id,
        source="upload",
        filename="test_video.mp4",
        video_path=video_path,
        status="processing",
        created_at=datetime.now(UTC),
        target_language="en",
        aspect_ratio="vertical_9_16"
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    print(f"Created job {job_id}, running pipeline...")
    
    # Run pipeline
    run_pipeline(job_id)

    db.refresh(job)
    print(f"Job status: {job.status}")
    if job.error:
        print(f"Error: {job.error}")
    
    db.close()

if __name__ == "__main__":
    test()
