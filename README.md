# Meeting Assist

Turn meeting audio or pasted notes into clear minutes: a summary, key points, decisions, and action items.

Upload a recording (or paste rough notes). The app transcribes with Whisper, then uses Claude to produce structured meeting notes you can browse, search, and export.

## Features

- **Audio upload** — mp3, wav, m4a, mp4, webm, and similar formats
- **Paste notes** — skip transcription and go straight to structured minutes
- **Transcription** — ffmpeg normalizes audio, then Whisper transcribes (optional speaker labels with a Hugging Face token)
- **Claude summaries** — summary, key points, decisions, action items, and topic tags
- **Meeting history** — list past meetings and search transcripts
- **Exports** — download Markdown or JSON minutes

## Requirements

- Python 3.12+
- Node.js 18+ (for the frontend)
- [ffmpeg](https://ffmpeg.org/) on your PATH
- An [Anthropic API key](https://console.anthropic.com/) for Claude

## Setup

### 1. Clone and configure env

```bash
cd "Meeting Assist"
cp .env.example .env
```

Edit `.env` and set your key:

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-5
WHISPER_MODEL=base
```

Optional:

```env
# Speaker-labeled transcripts (also needs: pip install pyannote.audio)
HF_TOKEN=hf_...
```

### 2. Backend

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Frontend

```bash
cd frontend
npm install
cd ..
```

## Run

One command (API + frontend):

```bash
./dev.sh
```

Or run them separately:

```bash
# Terminal 1 — API
source .venv/bin/activate
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 — UI
cd frontend
npm run dev
```

Open **http://127.0.0.1:5173**

- API docs: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

Ctrl+C in the `./dev.sh` terminal stops both services.

## How to use

1. Open the app and choose **Upload audio** or **Paste notes**.
2. Optionally add a title.
3. Click **Generate minutes** and wait — audio goes through Whisper, then Claude.
4. Review the summary, key points, decisions, and action items.
5. Use **Meetings** to browse history or search.
6. Download **Markdown** or **JSON** from a meeting’s detail page.

### CLI transcription only

You can still transcribe a file without the web app:

```bash
source .venv/bin/activate
python -m backend.services.transcribe_mp4 path/to/recording.mp4
```

## API overview

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/meetings/upload` | Upload audio → transcript + notes |
| `POST` | `/api/meetings/notes` | Paste text → notes |
| `GET` | `/api/meetings` | List meetings |
| `GET` | `/api/meetings/search?q=` | Search transcripts |
| `GET` | `/api/meetings/{id}` | Get one meeting |
| `GET` | `/api/meetings/{id}/export?format=markdown\|json` | Export minutes |

## Project layout

```
backend/           FastAPI app, models, Whisper + Claude services
frontend/          React + Vite UI
tests/             Spec-driven feature tests
spec.md            Original product spec
.env               Local secrets (not committed)
```

## Tests

```bash
source .venv/bin/activate
pytest tests/test_spec_features.py -v
```

Whisper and Claude are mocked in these tests so they stay fast.

## Notes

- First Whisper run may download the model and take longer.
- Longer recordings take more time to transcribe locally.
- `.env`, `uploads/`, and `*.db` are gitignored.
