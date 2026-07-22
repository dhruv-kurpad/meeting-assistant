# CLAUDE.md — Meeting Assist

Guidance for Claude (and other coding agents) working in this repo.

## What this project is

Local meeting-minutes app: upload audio or paste notes → Whisper transcript → Claude structured notes (summary, key points, decisions, action items, topics).

Stack:

- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Transcription:** `backend/services/transcribe_mp4.py` (ffmpeg normalize → Whisper; optional pyannote diarization)
- **LLM:** Anthropic Claude via `backend/services/llm_service.py`
- **Frontend:** React + Vite in `frontend/`
- **Spec:** `spec.md` (product requirements)
- **Tests:** `tests/test_spec_features.py` (mocks Whisper + Claude)

## Quick commands

```bash
# Both services
./dev.sh

# Tests
source .venv/bin/activate && pytest tests/test_spec_features.py -v

# CLI transcription only
python -m backend.services.transcribe_mp4 path/to/file.mp4
```

- UI: http://127.0.0.1:5173  
- API docs: http://127.0.0.1:8000/docs  

## Layout

```
backend/
  main.py                 # FastAPI app, CORS, dotenv
  database.py             # SQLite engine + sessions
  models.py               # Meeting, ActionItem
  schemas.py              # Pydantic request/response models
  routers/meeting.py      # All /api/meetings routes
  services/
    whisper_service.py    # Thin wrapper → transcribe_mp4
    transcribe_mp4.py     # ffmpeg + Whisper (+ optional diarization)
    llm_service.py        # Claude JSON notes
frontend/src/             # React UI (Home, Meetings, MeetingDetail)
tests/                    # Spec feature suite
dev.sh                    # Start API + frontend together
.env                      # Secrets (gitignored) — never commit
```

## Conventions

- Keep changes scoped to the request; don’t drive-by refactor.
- Prefer matching existing patterns in `backend/` and `frontend/src/`.
- Route order in `meeting.py` matters: list/search/upload/notes/export before `/{meeting_id}`.
- Structured LLM output must stay JSON-compatible with `{summary, key_points, decisions, action_items, topics}`.
- Frontend talks to the API via Vite proxy (`/api` → `:8000`); don’t hardcode production URLs.
- After backend API shape changes, update `tests/test_spec_features.py` and run pytest.
- SQLite schema is created with `Base.metadata.create_all` — if columns change in early dev, deleting `meetings.db` is OK.

## Secrets & env

Required in `.env`:

- `ANTHROPIC_API_KEY`
- Optional: `ANTHROPIC_MODEL`, `WHISPER_MODEL`, `HF_TOKEN` (speaker diarization)

Never commit `.env`, API keys, `uploads/`, or `*.db`. Use `.env.example` for templates only.

## Do not

- Commit secrets or real meeting audio from `uploads/`.
- Replace Claude with another provider unless asked.
- Bypass `transcribe_mp4.py` for a one-off Whisper call in the router — go through `whisper_service`.
- Add auth/multi-tenant/cloud deploy complexity unless requested.

## When changing features

1. Update backend (models/schemas/router/services as needed).
2. Update frontend pages/API client if the contract changed.
3. Extend or adjust `tests/test_spec_features.py`.
4. Update `README.md` if setup or usage changed.
5. Keep `spec.md` in mind; stretch goals already implemented: history, search, export, tags.
