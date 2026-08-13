import os
from datetime import UTC, datetime, timedelta

from backend.app.models.account import SocialAccount
from backend.app.models.persona import Persona, Post
from backend.app.services.scheduler import publish_scheduled_post


def test_scheduler_publishes_due_post(client, db, test_user, auth_headers, monkeypatch, tmp_path):
    # Enable dev publish mock
    monkeypatch.setenv("DEV_PUBLISH_MOCK", "true")

    user_obj, _ = test_user

    # Create persona
    persona = Persona(user_id=user_obj.id, name="Test Persona")
    db.add(persona)
    db.commit()
    db.refresh(persona)

    # Create an active social account
    account = SocialAccount(user_id=user_obj.id, platform="youtube", account_name="Dev YouTube", is_active=True)
    db.add(account)
    db.commit()
    db.refresh(account)

    # Create a dummy clip file
    upload_dir = os.environ.get("UPLOAD_DIR")
    clips_dir = os.path.join(upload_dir, "clips")
    os.makedirs(clips_dir, exist_ok=True)
    clip_path = os.path.join(clips_dir, "sched_sample.mp4")
    with open(clip_path, "wb") as f:
        f.write(b"dummy")

    # Create scheduled post in the past
    post = Post(
        persona_id=persona.id,
        user_id=user_obj.id,
        platform="youtube",
        title="Scheduled Test",
        body="scheduler publish test",
        media_path=clip_path,
        status="scheduled",
        scheduled_at=datetime.now(UTC) - timedelta(seconds=5),
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    # Run publish logic
    publish_scheduled_post(post, db)

    # Reload post
    db.refresh(post)
    assert post.status == "posted"
    assert post.posted_at is not None

    # Ensure publish log recorded
    from backend.app.core.config import settings

    log_path = settings.PUBLISH_LOG_PATH
    assert os.path.exists(log_path)
    with open(log_path) as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    assert any("Scheduled Test" in line or "sched_sample" in line for line in lines)
