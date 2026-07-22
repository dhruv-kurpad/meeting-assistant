from pathlib import Path

from backend.services.transcribe_mp4 import transcribe_file

ALLOWED_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".mp4",
    ".webm",
    ".ogg",
    ".flac",
    ".mpeg",
    ".mpga",
}


def is_allowed_audio(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def transcribe(audio_path: str | Path) -> str:
    """Delegate to transcribe_mp4 (ffmpeg normalize + Whisper, optional diarization)."""
    return transcribe_file(audio_path)
