from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
from .core.config import settings
from .core.transcriber import transcribe_video
from .core.analyst import analyze_transcript

app = FastAPI(title="Nexus-UGC Dashboard")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for processing results (for a simple prototype)
processing_results = {}

@app.post("/process")
async def process_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Uploads a video and triggers the AI transcription/analysis in the background."""
    process_id = str(uuid.uuid4())
    video_path = os.path.join(settings.UPLOAD_DIR, f"{process_id}_{file.filename}")
    
    # Save the uploaded file locally
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    processing_results[process_id] = {"status": "processing", "filename": file.filename}
    
    # Run the heavy AI logic in a background task
    background_tasks.add_task(run_pipeline, process_id, video_path)
    
    return {"process_id": process_id}

@app.get("/status/{process_id}")
async def get_status(process_id: str):
    """Checks the status and results of a video processing task."""
    result = processing_results.get(process_id)
    if not result:
        return JSONResponse(status_code=404, content={"error": "Process ID not found"})
    return result

async def run_pipeline(process_id: str, video_path: str):
    """Executes the Whisper -> Qwen pipeline with granular status updates."""
    try:
        # Step 1: Transcription
        processing_results[process_id]["status"] = "Extracting audio and transcribing..."
        transcript = transcribe_video(video_path)
        if not transcript:
            processing_results[process_id] = {"status": "error", "error": "Transcription failed"}
            return

        # Step 2: AI Analysis
        processing_results[process_id]["status"] = "Analyzing transcript for viral hooks (Ollama)..."
        analysis = analyze_transcript(transcript)
        if not analysis:
            processing_results[process_id] = {"status": "error", "error": "AI Analysis failed", "transcript": transcript}
            return

        # Success!
        processing_results[process_id] = {
            "status": "completed",
            "transcript": transcript,
            "analysis": analysis,
            "filename": os.path.basename(video_path)
        }
        
    except Exception as e:
        processing_results[process_id] = {"status": "error", "error": str(e)}
    finally:
        # Optionally cleanup the uploaded video after processing
        if os.path.exists(video_path):
            os.remove(video_path)

# Serve the frontend
app.mount("/", StaticFiles(directory=settings.FRONTEND_DIR, html=True), name="static")
