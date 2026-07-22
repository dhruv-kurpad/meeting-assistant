from pathlib import Path

import whisper

# Lazy-load so the API can start before the model is downloaded.
_model = None

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".mp4", ".webm", ".ogg", ".flac", ".mpeg", ".mpga"}


def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model("base")
    return _model


def is_allowed_audio(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def transcribe(audio_path: str | Path) -> str:
    model = get_model()
    result = model.transcribe(str(audio_path))
    return (result.get("text") or "").strip()
