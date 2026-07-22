# Meeting Assist — Project Spec

## Project overview

**Goal:** Upload a meeting audio file (or pasted notes) → get:

- Summary
- Key points
- Decisions
- Action items (with owner / due date if possible)

Build a small **FastAPI** backend + **React** (or simple HTML) frontend, using **Whisper** for transcription and an **LLM** (Ollama/local or API) for structured notes.

---

## High-level architecture

### Frontend

- **Upload page:** select audio file or paste text.
- **Result page:** show summary, bullets, decisions, action items.

### Backend (FastAPI)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/meetings/upload` | `POST` | Accept audio file, return meeting ID |
| `/api/meetings/{id}` | `GET` | Return transcript + structured notes |

### Pipeline

1. Validate file.
2. Run Whisper → transcript.
3. Run LLM → JSON with `{summary, key_points, decisions, action_items}`.
4. Store result (SQLite is enough).

### Models

**Meeting**

| Field | Description |
|-------|-------------|
| `id` | Primary key |
| `title` | Meeting title |
| `date` | Meeting date |
| `transcript` | Full transcript text |
| `summary` | LLM-generated summary |

**ActionItem**

| Field | Description |
|-------|-------------|
| `id` | Primary key |
| `meeting_id` | FK → Meeting |
| `owner` | Assignee (if detectable) |
| `description` | What needs to be done |
| `due_date` | Due date (if detectable) |

---

## Suggested tech stack

| Layer | Choice |
|-------|--------|
| Backend | Python, FastAPI, SQLAlchemy, SQLite |
| Transcription | `whisper` or `faster-whisper` |
| LLM (local) | Ollama (e.g. Llama 3 / Mistral) |
| LLM (API) | OpenAI / Gemini (optional) |
| Frontend | React + Vite, or a minimal HTML/JS page |

---

## Step-by-step build plan

### 1. Set up backend skeleton

Create FastAPI app:

```python
# backend/main.py
from fastapi import FastAPI
from routers import meeting

app = FastAPI()
app.include_router(meeting.router, prefix="/api/meetings")
```

Add models + SQLite:

```python
# backend/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

engine = create_engine("sqlite:///meetings.db")
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
```

Define `Meeting` and `ActionItem` tables.

### 2. Implement upload + processing route

```python
# backend/routers/meeting.py
from fastapi import APIRouter, UploadFile, File
from services import whisper_service, llm_service

router = APIRouter()

@router.post("/upload")
async def upload_meeting(file: UploadFile = File(...)):
    # 1. Save file
    # 2. Run Whisper → transcript
    transcript = whisper_service.transcribe(file)
    # 3. Run LLM → structured notes
    notes = llm_service.summarize(transcript)
    # 4. Save to DB, return meeting_id + notes
    return {"transcript": transcript, "notes": notes}
```

### 3. Add Whisper transcription

```python
# backend/services/whisper_service.py
import whisper

model = whisper.load_model("base")

def transcribe(file: UploadFile):
    audio_bytes = file.file.read()
    # save temp file, run model
    # return transcript string
```

You can swap to `faster-whisper` later for speed.

### 4. Add LLM summarization

```python
# backend/services/llm_service.py
import requests
import json

PROMPT = """
You are a meeting notes assistant.
Given the transcript, return strict JSON with:
- summary (string)
- key_points (list of strings)
- decisions (list of strings)
- action_items (list of {owner, description, due_date})
Transcript:
{transcript}
"""

def summarize(transcript: str):
    prompt = PROMPT.format(transcript=transcript)
    # Call Ollama or OpenAI here
    # Parse JSON and return Python dict
```

Use a fixed JSON schema so the frontend can render reliably.

### 5. Simple frontend

Minimal React page:

1. File input → `POST /api/meetings/upload`.
2. Show loading state.
3. Render:
   - **Summary** (paragraph)
   - **Key points** (bullets)
   - **Decisions** (bullets)
   - **Action items** (table: owner, description, due date)

You can copy the layout idea from existing meeting summarizer UIs for inspiration.

---

## Stretch goals (make it extra impressive)

- **History:** store meetings and show a “Meetings” list page.
- **Search:** simple text search over transcripts.
- **Exports:** button to download Markdown minutes or JSON.
- **Tags:** auto-extracted “topics” from the LLM.
