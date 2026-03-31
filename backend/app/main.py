from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
import re
from .core.config import settings
from .core.transcriber import transcribe_video
from .core.analyst import analyze_transcript
from .core.video_editor import cut_video

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

# In-memory storage for processing results
processing_results = {}

@app.post("/process")
async def process_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Uploads a video and triggers the AI pipeline."""
    process_id = str(uuid.uuid4())
    video_path = os.path.join(settings.UPLOAD_DIR, f"{process_id}_{file.filename}")
    
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    processing_results[process_id] = {
        "status": "Starting...", 
        "thinking": ["Initializing PubReelo pipeline...", "Allocating local resources..."],
        "filename": file.filename,
        "cancelled": False
    }
    
    background_tasks.add_task(run_pipeline, process_id, video_path)
    return {"process_id": process_id}

@app.post("/cancel/{process_id}")
async def cancel_processing(process_id: str):
    """Signals the pipeline to stop for a specific process ID."""
    if process_id in processing_results:
        processing_results[process_id]["cancelled"] = True
        processing_results[process_id]["status"] = "cancelled"
        return {"status": "Cancellation requested"}
    return JSONResponse(status_code=404, content={"error": "Process ID not found"})

@app.get("/status/{process_id}")
async def get_status(process_id: str):
    """Checks the status and results of a task."""
    result = processing_results.get(process_id)
    if not result:
        return JSONResponse(status_code=404, content={"error": "Process ID not found"})
    return result

def add_thought(process_id: str, thought: str):
    """Helper to add a 'thinking' log for the UI."""
    if process_id in processing_results:
        processing_results[process_id]["thinking"].append(thought)
        processing_results[process_id]["status"] = thought

async def run_pipeline(process_id: str, video_path: str):
    """Executes the pipeline with cancellation checks."""
    try:
        def check_cancelled():
            if processing_results.get(process_id, {}).get("cancelled"):
                raise Exception("Process cancelled by user")

        # Step 1: Transcription
        check_cancelled()
        add_thought(process_id, "Brain is warming up... extracting audio frequencies.")
        add_thought(process_id, "Whisper.cpp is now listening to your content...")
        transcript = transcribe_video(video_path)
        if not transcript:
            processing_results[process_id].update({"status": "error", "error": "Transcription failed"})
            return

        # Step 2: AI Analysis (JSON)
        check_cancelled()
        add_thought(process_id, "Got the transcript! Decoding the viral potential...")
        add_thought(process_id, "Consulting with Qwen3:30b for retention strategies.")
        analysis = analyze_transcript(transcript)
        
        if not analysis or "hooks" not in analysis:
            processing_results[process_id].update({"status": "error", "error": "AI Analysis failed to find hooks."})
            return

        # Step 3: Video Cutting
        check_cancelled()
        add_thought(process_id, f"Found {len(analysis.get('hooks', []))} potential goldmines.")
        add_thought(process_id, "FFmpeg is performing frame-accurate surgery...")
        clips = cut_video(video_path, analysis["hooks"])
        
        if not clips:
             processing_results[process_id].update({"status": "error", "error": "FFmpeg failed to generate clips."})
             return

        # Success!
        check_cancelled()
        processing_results[process_id].update({
            "status": "completed",
            "transcript": transcript,
            "analysis": analysis,
            "clips": clips,
            "filename": os.path.basename(video_path)
        })
        print(f"Pipeline completed for {process_id}")
        
    except Exception as e:
        status = "cancelled" if str(e) == "Process cancelled by user" else "error"
        processing_results[process_id].update({"status": status, "error": str(e)})
    finally:
        if os.path.exists(video_path):
            os.remove(video_path)

# Serve the frontend
app.mount("/", StaticFiles(directory=settings.FRONTEND_DIR, html=True), name="static")
