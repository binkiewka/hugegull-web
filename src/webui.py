from __future__ import annotations

import os
import sys
import asyncio
import json
import uuid
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import Config
from engine import Engine
from utils import utils
from info import info

app = FastAPI(title="HugeGull Web UI", version=info.version)

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
webui_dir = os.path.join(os.path.dirname(__file__), "webui")
if os.path.exists(webui_dir):
    app.mount("/static", StaticFiles(directory=webui_dir), name="static")

# Job storage
jobs: dict[str, JobStatus] = {}


@dataclass
class JobStatus:
    job_id: str
    status: str  # "pending", "running", "completed", "failed"
    url: str
    name: str
    progress: list[str] = field(default_factory=list)
    output_file: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None


class WebUIEngine(Engine):
    """Extended engine with progress callbacks for web UI"""
    
    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id
    
    def log(self, message: str) -> None:
        """Log progress to job status"""
        if self.job_id in jobs:
            jobs[self.job_id].progress.append(message)
        # Also print to console
        print(f"[{self.job_id}] {message}")
    
    def prepare(self) -> None:
        os.makedirs(config.project_dir, exist_ok=True)
        os.makedirs(config.output_dir, exist_ok=True)

        self.file = os.path.join(config.output_dir, f"{config.name}.mp4")
        counter = 1

        while os.path.exists(self.file):
            self.file = os.path.join(config.output_dir, f"{config.name}_{counter}.mp4")
            counter += 1
        
        self.log(f"Output file: {self.file}")


async def run_generation(job_id: str, url: str, name: str, settings: dict) -> None:
    """Run video generation in background"""
    job = jobs[job_id]
    job.status = "running"
    
    try:
        # Create a fresh config for this job
        global config
        original_config = config
        
        config = Config()
        config.urls = [url]
        config.name = name
        
        # Apply settings
        if "duration" in settings:
            config.duration = float(settings["duration"])
        if "fps" in settings:
            config.fps = int(settings["fps"])
        if "crf" in settings:
            config.crf = int(settings["crf"])
        if "min_clip_duration" in settings:
            config.min_clip_duration = float(settings["min_clip_duration"])
        if "max_clip_duration" in settings:
            config.max_clip_duration = float(settings["max_clip_duration"])
        if "avg_clip_duration" in settings:
            config.avg_clip_duration = float(settings["avg_clip_duration"])
        if "gpu" in settings:
            config.gpu = settings["gpu"]
        if "fade" in settings:
            config.fade = float(settings["fade"])
        
        job.progress.append(f"Starting: {name} | {int(config.duration)}s")
        
        engine = WebUIEngine(job_id)
        success = engine.start()
        
        if success:
            job.status = "completed"
            job.output_file = engine.file
            job.completed_at = datetime.now().isoformat()
            job.progress.append(f"✅ Saved: {engine.file}")
        else:
            job.status = "failed"
            job.error = "Generation failed - check sources"
            job.progress.append("❌ Failed: No valid sources found")
            
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        job.progress.append(f"❌ Error: {e}")
    
    # Cleanup
    try:
        import shutil
        shutil.rmtree(config.project_dir, ignore_errors=True)
    except:
        pass


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page"""
    html_path = os.path.join(os.path.dirname(__file__), "webui", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r") as f:
            return f.read()
    return HTMLResponse(content=get_default_html())


@app.get("/api/status")
async def get_all_jobs():
    """Get all job statuses"""
    return {job_id: {
        "job_id": j.job_id,
        "status": j.status,
        "url": j.url,
        "name": j.name,
        "progress": j.progress[-20:],  # Last 20 messages
        "output_file": j.output_file,
        "error": j.error,
        "created_at": j.created_at,
        "completed_at": j.completed_at,
    } for job_id, j in jobs.items()}


@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    """Get specific job status"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return {
        "job_id": job.job_id,
        "status": job.status,
        "url": job.url,
        "name": job.name,
        "progress": job.progress,
        "output_file": job.output_file,
        "error": job.error,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
    }


@app.post("/api/generate")
async def generate_video(background_tasks: BackgroundTasks, request: dict):
    """Start a new video generation job"""
    url = request.get("url")
    name = request.get("name")
    settings = request.get("settings", {})
    
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    if not name:
        name = utils.get_random_name()
    
    job_id = str(uuid.uuid4())[:8]
    
    job = JobStatus(
        job_id=job_id,
        status="pending",
        url=url,
        name=name,
    )
    jobs[job_id] = job
    
    # Start background task
    background_tasks.add_task(run_generation, job_id, url, name, settings)
    
    return {"job_id": job_id, "status": "pending", "name": name}


@app.get("/api/download/{job_id}")
async def download_video(job_id: str):
    """Download the generated video"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if job.status != "completed" or not job.output_file:
        raise HTTPException(status_code=400, detail="Video not ready")
    
    if not os.path.exists(job.output_file):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        job.output_file,
        media_type="video/mp4",
        filename=f"{job.name}.mp4"
    )


@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket for real-time progress updates"""
    await websocket.accept()
    
    if job_id not in jobs:
        await websocket.send_json({"error": "Job not found"})
        await websocket.close()
        return
    
    last_progress_len = 0
    
    try:
        while True:
            job = jobs[job_id]
            
            # Send new progress messages
            if len(job.progress) > last_progress_len:
                new_messages = job.progress[last_progress_len:]
                await websocket.send_json({
                    "status": job.status,
                    "progress": new_messages,
                    "output_file": job.output_file,
                    "error": job.error,
                })
                last_progress_len = len(job.progress)
            
            # Check if job is complete
            if job.status in ("completed", "failed"):
                await websocket.send_json({
                    "status": job.status,
                    "progress": [],
                    "output_file": job.output_file,
                    "error": job.error,
                })
                break
            
            await asyncio.sleep(0.5)
            
    except WebSocketDisconnect:
        pass


def get_default_html():
    """Default HTML if file not found"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>HugeGull Web UI</title>
        <meta charset="utf-8">
        <style>
            body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        </style>
    </head>
    <body>
        <h1>HugeGull Web UI</h1>
        <p>Loading...</p>
    </body>
    </html>
    """


def main():
    """Run the web UI server"""
    import argparse
    
    parser = argparse.ArgumentParser(description="HugeGull Web UI")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()
    
    print(f"🚀 Starting HugeGull Web UI...")
    print(f"   Open http://localhost:{args.port} in your browser")
    print(f"   Press Ctrl+C to stop")
    
    uvicorn.run(
        "webui:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
