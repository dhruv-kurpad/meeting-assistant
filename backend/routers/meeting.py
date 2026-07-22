import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Meeting
from backend.schemas import MeetingOut, UploadResponse
from backend.services import whisper_service

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload", response_model=UploadResponse)
async def upload_meeting(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    if not whisper_service.is_allowed_audio(file.filename):
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. Allowed: "
                + ", ".join(sorted(whisper_service.ALLOWED_EXTENSIONS))
            ),
        )

    suffix = Path(file.filename).suffix.lower()
    saved_name = f"{uuid.uuid4().hex}{suffix}"
    saved_path = UPLOAD_DIR / saved_name

    try:
        with saved_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)
    finally:
        await file.close()

    try:
        transcript = whisper_service.transcribe(saved_path)
    except Exception as exc:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc

    meeting_title = (title or Path(file.filename).stem or "Untitled Meeting").strip()
    meeting = Meeting(
        title=meeting_title,
        transcript=transcript,
        audio_path=str(saved_path),
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return UploadResponse(
        meeting_id=meeting.id,
        title=meeting.title,
        transcript=meeting.transcript or "",
    )


@router.get("/{meeting_id}", response_model=MeetingOut)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    meeting = db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    return meeting
