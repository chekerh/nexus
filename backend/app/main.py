from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, UTC
import shutil
import os
import uuid
import re
import time
from .core.config import settings
from .core.transcriber import transcribe_video
from .core.analyst import analyze_transcript
from .core.video_editor import cut_video
from .core.account_store import AccountStore
from .core.account_group_store import AccountGroupStore
from .core.publisher import publish_clip, PublishHistoryStore, SUPPORTED_PLATFORMS
from .core.security import auth_manager, log_audit, require_auth, verify_auth
from .core.airllm_service import airllm_service
from .core.drive_downloader import download_drive_file, extract_drive_file_id

app = FastAPI(title="Nexus-UGC Dashboard")

# Serve generated clips
CLIPS_DIR = os.path.join(settings.UPLOAD_DIR, "clips")
os.makedirs(CLIPS_DIR, exist_ok=True)
app.mount("/video_clips", StaticFiles(directory=CLIPS_DIR), name="clips")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for processing results and active PIDs
processing_results = {}
active_pids = {} # {process_id: pid}
account_store = AccountStore(settings.ACCOUNTS_DB_PATH)
account_group_store = AccountGroupStore(settings.ACCOUNT_GROUPS_DB_PATH)
publish_history_store = PublishHistoryStore(settings.PUBLISH_LOG_PATH)


@app.on_event("startup")
async def warm_models_on_startup():
    backend = (settings.ANALYSIS_BACKEND or "ollama").strip().lower()
    if backend == "airllm" and settings.AIRLLM_WARM_ON_START:
        ok, message = airllm_service.ensure_loaded()
        status = "ready" if ok else "fallback-to-ollama"
        print(f"[startup] airllm warmup: {status} | {message}")


class AccountCreate(BaseModel):
    platform: str
    account_name: str
    auth_mode: str = "manual"
    notes: str = ""
    oauth_refresh_token: str = ""
    youtube_privacy_status: str = "private"
    instagram_user_id: str = ""
    instagram_access_token: str = ""
    tiktok_open_id: str = ""
    tiktok_refresh_token: str = ""
    tiktok_access_token: str = ""


class PublishRequest(BaseModel):
    platform: str
    account_id: str
    clip_filename: str
    title: str
    description: str = ""


class AccountGroupCreate(BaseModel):
    name: str
    description: str = ""
    account_ids: list = []


class AccountGroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    account_ids: list | None = None


class DriveProcessRequest(BaseModel):
    drive_url: str


class AuthSetupRequest(BaseModel):
    password: str


class AuthVerifyRequest(BaseModel):
    password: str


class SessionResponse(BaseModel):
    token: str
    expires_in: int = 86400  # 24 hours


# Allowed video file extensions and MIME types
ALLOWED_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.flv'}
ALLOWED_MIME_TYPES = {
    'video/mp4', 'video/quicktime', 'video/x-msvideo',
    'video/x-matroska', 'video/webm', 'video/x-m4v', 'video/x-flv'
}
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB


def _sanitize_account(account: dict) -> dict:
    copy = dict(account)
    token = copy.get("oauth_refresh_token", "")
    instagram_token = copy.get("instagram_access_token", "")
    tiktok_refresh = copy.get("tiktok_refresh_token", "")
    tiktok_access = copy.get("tiktok_access_token", "")
    copy["has_oauth_refresh_token"] = bool(token)
    copy["has_instagram_access_token"] = bool(instagram_token)
    copy["has_tiktok_refresh_token"] = bool(tiktok_refresh)
    copy["has_tiktok_access_token"] = bool(tiktok_access)
    copy.pop("oauth_refresh_token", None)
    copy.pop("instagram_access_token", None)
    copy.pop("tiktok_refresh_token", None)
    copy.pop("tiktok_access_token", None)
    return copy


def _validate_video_file(file: UploadFile) -> tuple[bool, str]:
    """Validate uploaded video file for security."""
    # Check file extension
    filename = file.filename or ""
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Invalid file extension. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"

    # Check MIME type
    content_type = file.content_type or ""
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        # Some browsers may send generic MIME types, so we log but don't strictly enforce
        print(f"Warning: Unusual MIME type {content_type} for {filename}")

    # Check filename for path traversal
    if '/' in filename or '\\' in filename or '..' in filename:
        return False, "Invalid filename - path traversal detected"

    return True, ""


# Security API Endpoints
@app.get("/auth/status")
async def auth_status():
    """Check if authentication is enabled."""
    return {
        "enabled": auth_manager.is_enabled(),
        "message": "Password protection is " + ("enabled" if auth_manager.is_enabled() else "disabled")
    }


@app.post("/auth/setup")
async def setup_auth(request: AuthSetupRequest):
    """Set up password protection."""
    if auth_manager.is_enabled():
        return JSONResponse(
            status_code=400,
            content={"error": "Authentication already enabled. Use change password endpoint."}
        )

    if len(request.password) < 8:
        return JSONResponse(
            status_code=400,
            content={"error": "Password must be at least 8 characters"}
        )

    success = auth_manager.setup_password(request.password)
    if success:
        log_audit("auth_enabled", {"action": "password_setup"})
        return {"message": "Password protection enabled"}
    return JSONResponse(status_code=500, content={"error": "Failed to set up password"})


@app.post("/auth/verify")
async def verify_auth_endpoint(request: AuthVerifyRequest):
    """Verify password and get session token."""
    if not auth_manager.is_enabled():
        return {"token": "no-auth-required", "expires_in": 0}

    if verify_auth(request.password):
        token = auth_manager.create_session()
        log_audit("auth_login", {"success": True})
        return {"token": token, "expires_in": 86400}
    else:
        log_audit("auth_login", {"success": False})
        return JSONResponse(status_code=401, content={"error": "Invalid password"})


@app.post("/auth/disable")
async def disable_auth(request: AuthVerifyRequest):
    """Disable password protection."""
    if not auth_manager.is_enabled():
        return {"message": "Authentication already disabled"}

    if auth_manager.remove_password(request.password):
        log_audit("auth_disabled", {"action": "password_removed"})
        return {"message": "Password protection disabled"}
    return JSONResponse(status_code=401, content={"error": "Invalid password"})


@app.get("/audit/log")
async def get_audit_log(limit: int = 100):
    """Get recent audit log entries."""
    return {"entries": log_audit(limit=limit)}


@app.post("/process")
async def process_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    endscreen_image: Optional[UploadFile] = File(None),
    cta_text: Optional[str] = Form("Link in bio to try it free.")
):
    """Uploads a video and triggers the AI pipeline."""
    # Validate file
    valid, error_msg = _validate_video_file(file)
    if not valid:
        log_audit("upload_rejected", {"filename": file.filename, "reason": error_msg}, success=False)
        return JSONResponse(status_code=400, content={"error": error_msg})

    process_id = str(uuid.uuid4())
    # Sanitize filename
    safe_filename = os.path.basename(file.filename or "video.mp4")
    video_path = os.path.join(settings.UPLOAD_DIR, f"{process_id}_{safe_filename}")

    # Check file size after writing
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = os.path.getsize(video_path)
    if file_size > MAX_FILE_SIZE:
        os.remove(video_path)
        log_audit("upload_rejected", {"filename": file.filename, "reason": "File too large"}, success=False)
        return JSONResponse(status_code=400, content={"error": f"File too large. Max size: {MAX_FILE_SIZE / (1024*1024*1024):.1f}GB"})

    log_audit("upload_accepted", {"process_id": process_id, "filename": file.filename, "size": file_size})

    # Handle end screen image if provided
    endscreen_path = None
    if endscreen_image:
        safe_img_name = os.path.basename(endscreen_image.filename or "endscreen.jpg")
        endscreen_path = os.path.join(settings.UPLOAD_DIR, f"{process_id}_endscreen_{safe_img_name}")
        with open(endscreen_path, "wb") as buffer:
            shutil.copyfileobj(endscreen_image.file, buffer)

    processing_results[process_id] = {
        "status": "Starting...",
        "thinking": ["System online. Preparing neural pathways..."],
        "filename": file.filename,
        "cancelled": False,
        "has_endscreen": endscreen_path is not None,
        "cta_text": cta_text or "Link in bio to try it free."
    }

    # We use a regular def for run_pipeline so it runs in a separate thread
    background_tasks.add_task(
        run_pipeline_sync,
        process_id,
        video_path,
        endscreen_path=endscreen_path,
        cta_text=cta_text or "Link in bio to try it free."
    )
    return {"process_id": process_id}

@app.post("/process-drive")
async def process_drive_video(background_tasks: BackgroundTasks, payload: DriveProcessRequest):
    """Downloads a video from Google Drive and triggers the AI pipeline."""
    drive_url = payload.drive_url.strip()
    
    # Validate URL
    file_id = extract_drive_file_id(drive_url)
    if not file_id:
        return JSONResponse(
            status_code=400, 
            content={"error": "Invalid Google Drive URL. Please provide a shareable Drive link."}
        )
    
    process_id = str(uuid.uuid4())
    
    processing_results[process_id] = {
        "status": "Starting...", 
        "thinking": ["System online. Preparing neural pathways..."],
        "filename": f"drive_video_{file_id[:8]}.mp4",
        "cancelled": False
    }
    
    # Download and process in background
    background_tasks.add_task(run_drive_pipeline_sync, process_id, drive_url)
    return {"process_id": process_id}


@app.post("/cancel/{process_id}")
async def cancel_processing(process_id: str):
    """Hard-kills the running subprocess group and cancels the task."""
    if process_id in processing_results:
        processing_results[process_id]["cancelled"] = True
        processing_results[process_id]["status"] = "cancelled"
        
        # Kill active subprocess group if any
        pid = active_pids.get(process_id)
        if pid:
            try:
                import signal
                # Use os.killpg to kill the entire group started with os.setsid
                os.killpg(os.getpgid(pid), signal.SIGKILL)
                print(f"Hard-killed process group for PID {pid}")
            except Exception as e:
                print(f"Failed to kill process group {pid}: {e}")
        
        return {"status": "Process terminated"}
    return JSONResponse(status_code=404, content={"error": "Process ID not found"})

@app.get("/status/{process_id}")
async def get_status(process_id: str):
    """Checks the status and results of a task."""
    result = processing_results.get(process_id)
    if not result:
        return JSONResponse(status_code=404, content={"error": "Process ID not found"})
    return result


@app.get("/platforms")
async def list_platforms():
    return {"platforms": SUPPORTED_PLATFORMS}


@app.get("/accounts")
async def list_accounts(platform: str | None = None):
    if platform and platform not in SUPPORTED_PLATFORMS:
        return JSONResponse(status_code=400, content={"error": "Unsupported platform"})
    accounts = account_store.list_accounts(platform)
    return {"accounts": [_sanitize_account(a) for a in accounts]}


@app.post("/accounts")
async def create_account(payload: AccountCreate):
    platform = payload.platform.lower().strip()
    if platform not in SUPPORTED_PLATFORMS:
        return JSONResponse(status_code=400, content={"error": "Unsupported platform"})

    account = account_store.create_account({
        "platform": platform,
        "account_name": payload.account_name.strip(),
        "auth_mode": payload.auth_mode.strip() or "manual",
        "notes": payload.notes.strip(),
        "oauth_refresh_token": payload.oauth_refresh_token.strip(),
        "youtube_privacy_status": payload.youtube_privacy_status.strip() or "private",
        "instagram_user_id": payload.instagram_user_id.strip(),
        "instagram_access_token": payload.instagram_access_token.strip(),
        "tiktok_open_id": payload.tiktok_open_id.strip(),
        "tiktok_refresh_token": payload.tiktok_refresh_token.strip(),
        "tiktok_access_token": payload.tiktok_access_token.strip(),
        "created_at": datetime.now(UTC).isoformat(),
    })
    return {"account": _sanitize_account(account)}


@app.delete("/accounts/{account_id}")
async def delete_account(account_id: str):
    ok = account_store.delete_account(account_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Account not found"})
    return {"status": "deleted"}


# Account Groups API
@app.get("/account-groups")
async def list_account_groups():
    """List all account groups with their associated accounts."""
    groups = account_group_store.list_groups()
    all_accounts = account_store.list_accounts()
    account_map = {a["id"]: a for a in all_accounts}

    result = []
    for group in groups:
        enriched = dict(group)
        enriched["accounts"] = [
            _sanitize_account(account_map.get(aid, {}))
            for aid in group.get("account_ids", [])
            if aid in account_map
        ]
        result.append(enriched)
    return {"groups": result}


@app.post("/account-groups")
async def create_account_group(payload: AccountGroupCreate):
    """Create a new account group."""
    group = account_group_store.create_group({
        "name": payload.name.strip(),
        "description": payload.description.strip(),
        "account_ids": payload.account_ids,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    })
    return {"group": group}


@app.put("/account-groups/{group_id}")
async def update_account_group(group_id: str, payload: AccountGroupUpdate):
    """Update an account group."""
    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.description is not None:
        updates["description"] = payload.description.strip()
    if payload.account_ids is not None:
        updates["account_ids"] = payload.account_ids
    updates["updated_at"] = datetime.now(UTC).isoformat()

    group = account_group_store.update_group(group_id, updates)
    if not group:
        return JSONResponse(status_code=404, content={"error": "Group not found"})
    return {"group": group}


@app.delete("/account-groups/{group_id}")
async def delete_account_group(group_id: str):
    """Delete an account group."""
    ok = account_group_store.delete_group(group_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Group not found"})
    return {"status": "deleted"}


@app.post("/account-groups/{group_id}/accounts/{account_id}")
async def add_account_to_group(group_id: str, account_id: str):
    """Add an account to a group."""
    # Verify both exist
    group = account_group_store.get_group(group_id)
    account = account_store.get_account(account_id)
    if not group:
        return JSONResponse(status_code=404, content={"error": "Group not found"})
    if not account:
        return JSONResponse(status_code=404, content={"error": "Account not found"})

    ok = account_group_store.add_account_to_group(group_id, account_id)
    if not ok:
        return JSONResponse(status_code=400, content={"error": "Failed to add account to group"})
    return {"status": "added"}


@app.delete("/account-groups/{group_id}/accounts/{account_id}")
async def remove_account_from_group(group_id: str, account_id: str):
    """Remove an account from a group."""
    ok = account_group_store.remove_account_from_group(group_id, account_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Group or account not found"})
    return {"status": "removed"}


@app.get("/publish/history")
async def publish_history():
    return {"history": publish_history_store.list()}


@app.post("/publish")
async def publish_to_social(payload: PublishRequest):
    platform = payload.platform.lower().strip()
    if platform not in SUPPORTED_PLATFORMS:
        return JSONResponse(status_code=400, content={"error": "Unsupported platform"})

    account = account_store.get_account(payload.account_id)
    if not account:
        return JSONResponse(status_code=404, content={"error": "Account not found"})

    if account.get("platform") != platform:
        return JSONResponse(status_code=400, content={"error": "Account/platform mismatch"})

    clip_path = os.path.join(CLIPS_DIR, payload.clip_filename)
    if not os.path.exists(clip_path):
        return JSONResponse(status_code=404, content={"error": "Clip not found"})

    result = publish_clip(
        platform=platform,
        account=account,
        video_path=clip_path,
        title=payload.title.strip(),
        description=payload.description.strip(),
    )

    row = {
        "platform": platform,
        "account_id": account["id"],
        "account_name": account.get("account_name"),
        "clip_filename": payload.clip_filename,
        "title": payload.title.strip(),
        "description": payload.description.strip(),
        "result": result,
        "created_at": datetime.now(UTC).isoformat(),
    }
    publish_history_store.append(row)

    return {"publish": row}

def get_ai_commentary(line: str) -> str:
    """Provides a human-like strategist thought based on live transcript lines."""
    line_lower = line.lower()
    
    # Simple semantic triggers for 'real talking' thoughts
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

def add_thought(process_id: str, thought: str):
    """Helper to add a 'thinking' log for the UI with narrative context."""
    if not process_id or process_id not in processing_results:
        return
        
    clean_thought = thought.strip()
    if not clean_thought:
        return

    # If it's a Whisper line, inject AI commentary
    if "Whisper Perception:" in clean_thought:
        # Extract the transcript text
        match = re.search(r'\]\s+(.*)', clean_thought)
        if match:
            commentary = get_ai_commentary(match.group(1))
            if commentary:
                # Add the commentary first to show it's 'thinking' about that line
                if not processing_results[process_id]["thinking"] or processing_results[process_id]["thinking"][-1] != commentary:
                    processing_results[process_id]["thinking"].append(commentary)

    # Avoid duplicate thoughts
    if not processing_results[process_id]["thinking"] or processing_results[process_id]["thinking"][-1] != clean_thought:
        processing_results[process_id]["thinking"].append(clean_thought)
        processing_results[process_id]["status"] = clean_thought
        # Keep it snappy
        if len(processing_results[process_id]["thinking"]) > 150:
            processing_results[process_id]["thinking"].pop(0)

def run_pipeline_sync(process_id: str, video_path: str):
    """Synchronous pipeline runner to allow thread-based background execution."""
    try:
        pipeline_t0 = time.perf_counter()
        timing = {
            "transcription_seconds": 0.0,
            "analysis_seconds": 0.0,
            "cutting_seconds": 0.0,
            "total_seconds": 0.0,
        }

        def check_cancelled():
            if processing_results.get(process_id, {}).get("cancelled"):
                raise Exception("Process cancelled by user")

        # Initial AI Strategy Thought
        check_cancelled()
        filename = processing_results[process_id]["filename"]
        add_thought(process_id, f"Scanning metadata... Video: '{filename}' detected.")
        add_thought(process_id, "Qwen Strategy: I'm going to look for high-energy peaks and semantic hooks that work for short-form retention.")

        # Step 1: Transcription
        check_cancelled()
        add_thought(process_id, "Whisper.cpp Perception: Listening to the audio track to map out the narrative structure...")
        t0 = time.perf_counter()
        
        # Pass add_thought as a callback
        transcript = transcribe_video(video_path, process_id, active_pids, thought_callback=add_thought)
        timing["transcription_seconds"] = round(time.perf_counter() - t0, 2)
        add_thought(process_id, f"Timing: Transcription finished in {timing['transcription_seconds']}s.")
        
        if not transcript:
            if not processing_results[process_id].get("cancelled"):
                processing_results[process_id].update({"status": "error", "error": "Transcription failed"})
            return

        # Step 2: AI Analysis
        check_cancelled()
        add_thought(process_id, "Semantic Analysis: Parsing transcript for 'scroll-stopper' moments...")
        t0 = time.perf_counter()
        analysis = analyze_transcript(transcript, video_path)
        timing["analysis_seconds"] = round(time.perf_counter() - t0, 2)
        add_thought(process_id, f"Timing: AI analysis finished in {timing['analysis_seconds']}s.")
        
        if not analysis or "hooks" not in analysis:
            processing_results[process_id].update({"status": "error", "error": "AI Analysis failed to find hooks."})
            return

        meta = analysis.get("analysis_meta", {})
        if meta:
            add_thought(
                process_id,
                f"Selection Engine: {meta.get('candidate_count', 0)} candidates ranked, {meta.get('scene_cut_count', 0)} scene boundaries used, backend={meta.get('backend', 'ollama')}, model={meta.get('model', 'n/a')}."
            )
            if meta.get("fallback_used"):
                add_thought(process_id, "Selection Engine: Model output format failed, heuristic fallback hooks were applied.")
            add_thought(
                process_id,
                f"Duration Optimizer: min={meta.get('duration_min', 0)}s avg={meta.get('duration_avg', 0)}s max={meta.get('duration_max', 0)}s."
            )

        # Step 3: Video Cutting
        check_cancelled()
        if "strategy_thought" in analysis:
            add_thought(process_id, f"Qwen Strategic Insight: {analysis['strategy_thought']}")
            
        add_thought(process_id, f"Editor Monologue: Found {len(analysis.get('hooks', []))} viral segments. Initiating surgical cuts.")
        t0 = time.perf_counter()
        clips = cut_video(video_path, analysis["hooks"], process_id, active_pids, thought_callback=add_thought, transcript=transcript)
        timing["cutting_seconds"] = round(time.perf_counter() - t0, 2)
        add_thought(process_id, f"Timing: Clip rendering finished in {timing['cutting_seconds']}s.")
        
        if not clips:
             if not processing_results[process_id].get("cancelled"):
                processing_results[process_id].update({"status": "error", "error": "FFmpeg failed to generate clips."})
             return

        # Success!
        check_cancelled()
        timing["total_seconds"] = round(time.perf_counter() - pipeline_t0, 2)
        add_thought(process_id, "Pipeline complete. All clips processed and verified.")
        processing_results[process_id].update({
            "status": "completed",
            "transcript": transcript,
            "analysis": analysis,
            "clips": clips,
            "timing": timing,
        })
        
    except Exception as e:
        status = "cancelled" if "cancelled" in str(e).lower() else "error"
        processing_results[process_id].update({"status": status, "error": str(e)})
    finally:
        active_pids.pop(process_id, None)
        if os.path.exists(video_path):
            os.remove(video_path)


def run_drive_pipeline_sync(process_id: str, drive_url: str):
    """Downloads from Google Drive then runs the standard pipeline."""
    video_path = None
    try:
        add_thought(process_id, f"Drive: Connecting to Google Drive...")
        
        # Download the video
        video_path = download_drive_file(
            drive_url, 
            settings.UPLOAD_DIR, 
            progress_callback=lambda msg: add_thought(process_id, msg)
        )
        
        if not video_path:
            processing_results[process_id].update({
                "status": "error", 
                "error": "Failed to download from Google Drive. Check that the file is shared and accessible."
            })
            return
        
        # Update filename in results
        processing_results[process_id]["filename"] = os.path.basename(video_path)
        
        # Run the standard pipeline
        add_thought(process_id, "Drive: Download complete. Starting AI pipeline...")
        run_pipeline_sync(process_id, video_path)
        
    except Exception as e:
        status = "cancelled" if "cancelled" in str(e).lower() else "error"
        processing_results[process_id].update({"status": status, "error": str(e)})
        # Clean up downloaded file if it exists
        if video_path and os.path.exists(video_path):
            os.remove(video_path)


# Serve the frontend
app.mount("/", StaticFiles(directory=settings.FRONTEND_DIR, html=True), name="static")
