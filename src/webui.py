from __future__ import annotations

import os
import sys
import asyncio
import json
import uuid
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field, asdict

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import Config
from engine import Engine, ClipSection
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
    can_resume: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None
    total_clips: int = 0
    completed_clips: int = 0
    clips: list[dict] = field(default_factory=list)  # For preview mode
    is_preview: bool = False


class WebUIEngine(Engine):
    """Extended engine with progress callbacks for web UI"""
    
    def __init__(self, job_id: str, job: JobStatus):
        super().__init__()
        self.job_id = job_id
        self.job = job
    
    def log(self, message: str) -> None:
        """Log progress to job status"""
        if self.job_id in jobs:
            jobs[self.job_id].progress.append(message)
        print(f"[{self.job_id}] {message}")
    
    def save_state(self) -> None:
        """Save state and update job progress"""
        super().save_state()
        if self.job_id in jobs:
            jobs[self.job_id].completed_clips = self.completed_clips
            jobs[self.job_id].total_clips = self.total_clips
            jobs[self.job_id].can_resume = True
    
    def show_preview(self) -> bool:
        """Override to send clips to web UI"""
        result = super().show_preview()
        
        if self.job_id in jobs:
            jobs[self.job_id].clips = [
                {
                    "start": s.start,
                    "duration": s.duration,
                    "scene_score": s.scene_score,
                    "index": s.index
                }
                for s in self.clip_sections
            ]
            jobs[self.job_id].total_clips = len(self.clip_sections)
        
        return result


async def run_generation(job_id: str, url: str, name: str, settings: dict) -> None:
    """Run video generation in background"""
    job = jobs[job_id]
    job.status = "running"
    job.is_preview = settings.get("preview", False) or settings.get("dry_run", False)
    
    try:
        # Create a fresh config for this job
        global config
        original_config = config
        
        config = Config()
        config.urls = [url]
        config.name = name
        
        # Apply settings
        config.duration = float(settings.get("duration", 45))
        config.fps = int(settings.get("fps", 30))
        config.crf = int(settings.get("crf", 28))
        config.min_clip_duration = float(settings.get("min_clip_duration", 3))
        config.max_clip_duration = float(settings.get("max_clip_duration", 9))
        config.avg_clip_duration = float(settings.get("avg_clip_duration", 6))
        config.gpu = settings.get("gpu", "")
        config.fade = float(settings.get("fade", 0.03))
        
        # New features
        config.scene_detection = settings.get("scene_detection", False)
        config.scene_threshold = float(settings.get("scene_threshold", 0.3))
        config.skip_start = float(settings.get("skip_start", 0))
        config.skip_end = float(settings.get("skip_end", 0))
        config.resume = settings.get("resume", False)
        config.shuffle_clips = settings.get("shuffle_clips", False)
        config.sort_by = settings.get("sort_by", "index")
        config.aspect_ratio = settings.get("aspect_ratio", "")
        config.output_format = settings.get("output_format", "mp4")
        config.preview = settings.get("preview", False)
        config.dry_run = settings.get("dry_run", False)
        
        job.log(f"Starting: {config.name} | {int(config.duration)}s")
        
        engine = WebUIEngine(job_id, job)
        success = engine.start()
        
        if success:
            job.status = "completed"
            job.output_file = engine.file
            job.completed_at = datetime.now().isoformat()
            job.total_clips = engine.total_clips
            job.completed_clips = engine.completed_clips
            
            if job.is_preview:
                job.log(f"✅ Preview complete - {len(engine.clip_sections)} clips planned")
            else:
                job.log(f"✅ Saved: {engine.file}")
        else:
            job.status = "failed"
            job.error = "Generation failed - check sources"
            job.can_resume = os.path.exists(os.path.join(config.project_dir, "state.json"))
            job.log("❌ Failed: No valid sources found or generation error")
            
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        job.can_resume = True  # Assume we can resume on error
        job.log(f"❌ Error: {e}")
    
    # Cleanup on success (not on failure to allow resume)
    if job.status == "completed" and not job.is_preview:
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
        "progress": j.progress[-20:],
        "output_file": j.output_file,
        "error": j.error,
        "can_resume": j.can_resume,
        "created_at": j.created_at,
        "completed_at": j.completed_at,
        "total_clips": j.total_clips,
        "completed_clips": j.completed_clips,
        "is_preview": j.is_preview,
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
        "can_resume": job.can_resume,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "total_clips": job.total_clips,
        "completed_clips": job.completed_clips,
        "clips": job.clips,
        "is_preview": job.is_preview,
    }


@app.post("/api/generate")
async def generate_video(background_tasks: BackgroundTasks, request: dict):
    """Start a new video generation job"""
    url = request.get("url")
    name = request.get("name")
    settings = request.get("settings", {})
    
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    job_id = str(uuid.uuid4())[:8]
    
    job = JobStatus(
        job_id=job_id,
        status="pending",
        url=url,
        name=name or f"job_{job_id}",
        is_preview=settings.get("preview", False) or settings.get("dry_run", False),
    )
    jobs[job_id] = job
    
    # Start background task
    background_tasks.add_task(run_generation, job_id, url, name or f"job_{job_id}", settings)
    
    return {"job_id": job_id, "status": "pending", "name": job.name, "is_preview": job.is_preview}


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
            
            # Prepare response data
            response = {
                "status": job.status,
                "progress": [],
                "output_file": job.output_file,
                "error": job.error,
                "can_resume": job.can_resume,
                "total_clips": job.total_clips,
                "completed_clips": job.completed_clips,
            }
            
            # Send new progress messages
            if len(job.progress) > last_progress_len:
                response["progress"] = job.progress[last_progress_len:]
                last_progress_len = len(job.progress)
            
            # Include clips for preview mode
            if job.is_preview and job.clips:
                response["clips"] = job.clips
            
            await websocket.send_json(response)
            
            # Check if job is complete
            if job.status in ("completed", "failed"):
                # Send one final update
                await websocket.send_json({
                    "status": job.status,
                    "progress": [],
                    "output_file": job.output_file,
                    "error": job.error,
                    "can_resume": job.can_resume,
                    "total_clips": job.total_clips,
                    "completed_clips": job.completed_clips,
                    "clips": job.clips if job.is_preview else [],
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
    parser.add_argument("--port", type=int, default=28472, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()
    
    print(f"🚀 Starting HugeGull Web UI...")
    print(f"   Open http://localhost:{args.port} in your browser")
    print(f"   Or: hugegull-web --port <number> to use a different port")
    print(f"   Press Ctrl+C to stop")
    
    uvicorn.run(
        "webui:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
