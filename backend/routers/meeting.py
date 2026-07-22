from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import ActionItem, Meeting
from backend.schemas import (
    MeetingListItem,
    MeetingOut,
    StructuredNotes,
    TextNotesRequest,
    UploadResponse,
)
from backend.services import llm_service, whisper_service

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _apply_notes(meeting: Meeting, notes: dict[str, Any], db: Session) -> StructuredNotes:
    meeting.summary = notes.get("summary") or ""
    meeting.key_points = list(notes.get("key_points") or [])
    meeting.decisions = list(notes.get("decisions") or [])
    meeting.tags = list(notes.get("topics") or notes.get("tags") or [])

    for existing in list(meeting.action_items):
        db.delete(existing)
    db.flush()

    structured_items = []
    for raw in notes.get("action_items") or []:
        item = ActionItem(
            owner=raw.get("owner"),
            description=raw["description"],
            due_date=raw.get("due_date"),
        )
        meeting.action_items.append(item)
        structured_items.append(
            {
                "owner": raw.get("owner"),
                "description": raw["description"],
                "due_date": raw.get("due_date"),
            }
        )

    return StructuredNotes(
        summary=meeting.summary or "",
        key_points=list(meeting.key_points or []),
        decisions=list(meeting.decisions or []),
        action_items=structured_items,
        topics=list(meeting.tags or []),
    )


def _summarize_or_raise(transcript: str) -> dict[str, Any]:
    try:
        return llm_service.summarize(transcript)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM summarization failed: {exc}") from exc


def _meeting_out(meeting: Meeting) -> MeetingOut:
    return MeetingOut.from_meeting(meeting)


@router.get("", response_model=list[MeetingListItem])
@router.get("/", response_model=list[MeetingListItem])
def list_meetings(db: Session = Depends(get_db)):
    meetings = db.query(Meeting).order_by(Meeting.date.desc()).all()
    return [
        MeetingListItem(
            id=m.id,
            title=m.title,
            date=m.date,
            summary=m.summary,
            tags=list(m.tags or []),
        )
        for m in meetings
    ]


@router.get("/search")
def search_meetings(q: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    needle = q.strip()
    if not needle:
        raise HTTPException(status_code=400, detail="Query q is required.")

    pattern = f"%{needle}%"
    meetings = (
        db.query(Meeting)
        .filter(
            or_(
                Meeting.transcript.ilike(pattern),
                Meeting.title.ilike(pattern),
                Meeting.summary.ilike(pattern),
            )
        )
        .order_by(Meeting.date.desc())
        .all()
    )
    return {
        "meetings": [
            MeetingListItem(
                id=m.id,
                title=m.title,
                date=m.date,
                summary=m.summary,
                tags=list(m.tags or []),
            )
            for m in meetings
        ]
    }


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

    notes_dict = _summarize_or_raise(transcript)
    meeting_title = (title or Path(file.filename).stem or "Untitled Meeting").strip()
    meeting = Meeting(
        title=meeting_title,
        transcript=transcript,
        audio_path=str(saved_path),
    )
    db.add(meeting)
    db.flush()
    notes = _apply_notes(meeting, notes_dict, db)
    db.commit()
    db.refresh(meeting)

    return UploadResponse(
        meeting_id=meeting.id,
        title=meeting.title,
        transcript=meeting.transcript or "",
        notes=notes,
    )


@router.post("/notes", response_model=UploadResponse)
def create_from_text(payload: TextNotesRequest, db: Session = Depends(get_db)):
    transcript = payload.text.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="text must not be empty.")

    notes_dict = _summarize_or_raise(transcript)
    meeting = Meeting(
        title=(payload.title or "Pasted Notes").strip() or "Pasted Notes",
        transcript=transcript,
    )
    db.add(meeting)
    db.flush()
    notes = _apply_notes(meeting, notes_dict, db)
    db.commit()
    db.refresh(meeting)

    return UploadResponse(
        meeting_id=meeting.id,
        title=meeting.title,
        transcript=meeting.transcript or "",
        notes=notes,
    )


@router.post("/text", response_model=UploadResponse)
def create_from_text_alias(payload: TextNotesRequest, db: Session = Depends(get_db)):
    return create_from_text(payload, db)


@router.get("/{meeting_id}/export")
def export_meeting(
    meeting_id: int,
    format: str = Query(default="markdown", pattern="^(markdown|json|md)$"),
    db: Session = Depends(get_db),
):
    meeting = (
        db.query(Meeting)
        .options(joinedload(Meeting.action_items))
        .filter(Meeting.id == meeting_id)
        .first()
    )
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")

    fmt = "json" if format == "json" else "markdown"
    if fmt == "json":
        payload = _meeting_out(meeting).model_dump(mode="json")
        return Response(
            content=json.dumps(payload, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="meeting-{meeting_id}.json"'
            },
        )

    lines = [
        f"# {meeting.title}",
        "",
        f"_Date: {meeting.date}_",
        "",
        "## Summary",
        meeting.summary or "_No summary_",
        "",
        "## Key points",
    ]
    for point in meeting.key_points or []:
        lines.append(f"- {point}")
    if not meeting.key_points:
        lines.append("- _None_")

    lines.extend(["", "## Decisions"])
    for decision in meeting.decisions or []:
        lines.append(f"- {decision}")
    if not meeting.decisions:
        lines.append("- _None_")

    lines.extend(["", "## Action items", ""])
    if meeting.action_items:
        lines.append("| Owner | Description | Due date |")
        lines.append("| --- | --- | --- |")
        for item in meeting.action_items:
            lines.append(
                f"| {item.owner or '—'} | {item.description} | {item.due_date or '—'} |"
            )
    else:
        lines.append("_None_")

    tags = meeting.tags or []
    if tags:
        lines.extend(["", "## Topics", ", ".join(tags)])

    lines.extend(["", "## Transcript", "", meeting.transcript or "_Empty_"])
    body = "\n".join(lines) + "\n"
    return PlainTextResponse(
        content=body,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="meeting-{meeting_id}.md"'
        },
    )


@router.get("/{meeting_id}/export.md")
def export_meeting_md(meeting_id: int, db: Session = Depends(get_db)):
    return export_meeting(meeting_id, format="markdown", db=db)


@router.get("/{meeting_id}/export.json")
def export_meeting_json(meeting_id: int, db: Session = Depends(get_db)):
    return export_meeting(meeting_id, format="json", db=db)


@router.get("/{meeting_id}", response_model=MeetingOut)
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    meeting = (
        db.query(Meeting)
        .options(joinedload(Meeting.action_items))
        .filter(Meeting.id == meeting_id)
        .first()
    )
    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found.")
    return _meeting_out(meeting)
