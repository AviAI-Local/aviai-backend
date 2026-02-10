import subprocess
import os
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from agent.session.service import SessionService
from database.config import get_db
from database.model import Session

router = APIRouter()

load_dotenv()

def get_recordings_dir() -> str:
    """Get recordings directory, resolving relative paths from project root."""
    recordings_dir = os.getenv('RECORDING_DB_URL', './recordings')
    if not os.path.isabs(recordings_dir):
        # view.py is at src/agent/recording/view.py, so 4 levels up to project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        recordings_dir = os.path.join(project_root, recordings_dir.lstrip("./"))
    return recordings_dir

class RecordingRequest(BaseModel):
    file: UploadFile
    session_id: str

@router.post("/upload-audio")
async def upload_audio(
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    try:
        # Get recording directory
        recording_dir = get_recordings_dir()
        os.makedirs(recording_dir, exist_ok=True)

        wav_filename = f"{session_id}.wav"
        wav_path = os.path.join(recording_dir, wav_filename)

        mp3_filename = wav_filename.replace(".wav", ".mp3")
        mp3_path = os.path.join(recording_dir, mp3_filename)

        if os.path.exists(mp3_path):
            os.remove(mp3_path)

        # Save the uploaded WAV file
        with open(wav_path, "wb") as f:
            f.write(await file.read())

        # Convert to MP3 using ffmpeg
        command = ["ffmpeg", "-y", "-i", wav_path, "-codec:a", "libmp3lame", "-qscale:a", "2", mp3_path]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr.decode()}")
            raise Exception(f"FFmpeg conversion failed: {result.stderr.decode()}")

        # Delete the original .wav to save space
        if os.path.exists(wav_path):
            os.remove(wav_path)

        service = SessionService(db)
        service.update_session(session_id, {'recording': mp3_filename})

        return {
            "message": "Audio converted successfully",
            "mp3_url": f"/recordings/{mp3_filename}"
        }

    except Exception as e:
        print(f"Upload audio error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/upload-video")
async def upload_video(
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    try:
        # Get recording directory
        recording_dir = get_recordings_dir()
        print(f"Recording directory: {recording_dir}")
        os.makedirs(recording_dir, exist_ok=True)

        # File paths
        webm_filename = f"{session_id}.webm"
        webm_path = os.path.join(recording_dir, webm_filename)

        mp4_filename = webm_filename.replace(".webm", ".mp4")
        mp4_path = os.path.join(recording_dir, mp4_filename)

        print(f"Saving webm to: {webm_path}")
        print(f"Will convert to: {mp4_path}")

        # Remove existing output if needed
        if os.path.exists(mp4_path):
            os.remove(mp4_path)

        # Save uploaded .webm file
        with open(webm_path, "wb") as f:
            f.write(await file.read())

        # FFmpeg: convert .webm to .mp4
        command = [
            "ffmpeg", "-y",
            "-i", webm_path,
            "-c:v", "libx264",
            "-preset", "fast",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            mp4_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr.decode()}")
            raise Exception(f"FFmpeg conversion failed: {result.stderr.decode()}")

        # Delete the original .webm to save space
        if os.path.exists(webm_path):
            os.remove(webm_path)

        service = SessionService(db)
        service.update_session(session_id, {'recording': mp4_filename})

        return {
            "message": "Video converted successfully",
            "video_url": f"{mp4_filename}"
        }

    except Exception as e:
        print(f"Upload video error: {e}")
        raise HTTPException(status_code=500, detail=str(e))