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

# In-memory storage for processing results and active PIDs
processing_results = {}
active_pids = {} # {process_id: pid}

@app.post("/process")
async def process_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Uploads a video and triggers the AI pipeline."""
    process_id = str(uuid.uuid4())
    video_path = os.path.join(settings.UPLOAD_DIR, f"{process_id}_{file.filename}")
    
    with open(video_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    processing_results[process_id] = {
        "status": "Starting...", 
        "thinking": ["System online. Preparing neural pathways..."],
        "filename": file.filename,
        "cancelled": False
    }
    
    # We use a regular def for run_pipeline so it runs in a separate thread
    background_tasks.add_task(run_pipeline_sync, process_id, video_path)
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
        
        # Pass add_thought as a callback
        transcript = transcribe_video(video_path, process_id, active_pids, thought_callback=add_thought)
        
        if not transcript:
            if not processing_results[process_id].get("cancelled"):
                processing_results[process_id].update({"status": "error", "error": "Transcription failed"})
            return

        # Step 2: AI Analysis
        check_cancelled()
        add_thought(process_id, "Semantic Analysis: Parsing transcript for 'scroll-stopper' moments...")
        analysis = analyze_transcript(transcript)
        
        if not analysis or "hooks" not in analysis:
            processing_results[process_id].update({"status": "error", "error": "AI Analysis failed to find hooks."})
            return

        # Step 3: Video Cutting
        check_cancelled()
        if "strategy_thought" in analysis:
            add_thought(process_id, f"Qwen Strategic Insight: {analysis['strategy_thought']}")
            
        add_thought(process_id, f"Editor Monologue: Found {len(analysis.get('hooks', []))} viral segments. Initiating surgical cuts.")
        clips = cut_video(video_path, analysis["hooks"], process_id, active_pids, thought_callback=add_thought)
        
        if not clips:
             if not processing_results[process_id].get("cancelled"):
                processing_results[process_id].update({"status": "error", "error": "FFmpeg failed to generate clips."})
             return

        # Success!
        check_cancelled()
        add_thought(process_id, "Pipeline complete. All clips processed and verified.")
        processing_results[process_id].update({
            "status": "completed",
            "transcript": transcript,
            "analysis": analysis,
            "clips": clips
        })
        
    except Exception as e:
        status = "cancelled" if "cancelled" in str(e).lower() else "error"
        processing_results[process_id].update({"status": status, "error": str(e)})
    finally:
        active_pids.pop(process_id, None)
        if os.path.exists(video_path):
            os.remove(video_path)

# Serve the frontend
app.mount("/", StaticFiles(directory=settings.FRONTEND_DIR, html=True), name="static")
