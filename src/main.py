import os
import subprocess
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from handlers.performance_analysis.view import router as performance_analysis_router

from account.view import router as account_router
from auth.view import router as auth_router
from note.view import router as note_router
from scenario.view import router as scenario_router
from handlers.document_process.view import router as documents_router
from agent.session.view import router as session_router
from handlers.conversation_analysis.view import router as analysis_router
from agent.history.view import router as history_router
from agent.recording.view import router as recording_router
from agent.prompt.view import router as prompt_router
from agent.models import init_models


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: run pending DB migrations. Done here rather than before
    # uvicorn starts, so the server socket opens immediately — Render's
    # free tier has no pre-deploy step, and it fails deploys that don't
    # bind a port quickly.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=project_root, check=True)

    init_models()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(title="Cognitive Interview API", lifespan=lifespan)

# CORS for frontend. Defaults cover local dev; set CORS_ALLOWED_ORIGINS
# (comma-separated) in the deploy environment to add the deployed frontend
# origin(s) without a code change.
_default_origins = "http://localhost:3000,https://aviai-frontend.onrender.com"
allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_router, prefix="/api/v1/account", tags=["account"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(note_router, prefix="/api/v1/note", tags=["note"])
app.include_router(documents_router, prefix="/api/v1/document", tags=["documents"])
app.include_router(scenario_router, prefix="/api/v1/scenario", tags=["scenario"])
app.include_router(performance_analysis_router,prefix="/api/v1/performance-analysis",tags=["performance-analysis"])
app.include_router(analysis_router, prefix="/api/v1/analysis", tags=["analysis"]) 
app.include_router(session_router, prefix="/api/v1/session", tags=["session"]) 
app.include_router(history_router, prefix="/api/v1/conversation", tags=["conversation"]) 
app.include_router(recording_router, prefix="/api/v1/recording", tags=["recording"])
app.include_router(prompt_router, prefix="/api/v1/prompt", tags=["prompt"])

# Serve static recordings
recordings_dir = os.getenv("RECORDING_DB_URL", "./recordings")
# For relative paths, resolve from project root (parent of src/)
if not os.path.isabs(recordings_dir):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    recordings_dir = os.path.join(project_root, recordings_dir.lstrip("./"))
os.makedirs(recordings_dir, exist_ok=True)
app.mount("/recordings", StaticFiles(directory=recordings_dir), name="recordings")

