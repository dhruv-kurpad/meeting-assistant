"""
Meeting transcription helpers (ffmpeg normalize + Whisper).

Optional speaker diarization via pyannote when HF_TOKEN is set in .env.
Also usable as a CLI:
  python -m backend.services.transcribe_mp4 <file.mp4>
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import whisper
from dotenv import load_dotenv

load_dotenv()

_model = None


def get_whisper_model(model_name: str | None = None):
    global _model
    name = model_name or os.getenv("WHISPER_MODEL", "base")
    # Reload if model name changes between calls in the same process.
    if _model is None or getattr(_model, "_meeting_assist_name", None) != name:
        _model = whisper.load_model(name)
        _model._meeting_assist_name = name
    return _model


def extract_audio(input_path: str | Path, wav_path: str | Path) -> None:
    """Convert any ffmpeg-readable media to 16kHz mono WAV."""
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(wav_path),
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="ignore")[-800:]
        raise RuntimeError(f"ffmpeg failed to extract audio: {err}")


def transcribe_audio(audio_path: str | Path) -> str:
    """Plain Whisper transcription (no diarization)."""
    model = get_whisper_model()
    result = model.transcribe(str(audio_path))
    return (result.get("text") or "").strip()


def _hf_token() -> str | None:
    token = (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACE_TOKEN")
        or os.getenv("HUGGING_FACE_HUB_TOKEN")
        or ""
    ).strip()
    return token or None


def diarize_audio(audio_path: str | Path):
    """Requires HuggingFace access + pyannote.audio."""
    token = _hf_token()
    if not token:
        raise RuntimeError(
            "Speaker diarization needs HF_TOKEN in .env "
            "(https://huggingface.co/settings/tokens)."
        )

    try:
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise RuntimeError(
            "pyannote.audio is not installed. "
            "Install it to enable speaker diarization."
        ) from exc

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        token=token,
    )
    return pipeline(str(audio_path))


def transcribe_with_speakers(audio_path: str | Path) -> str:
    """Whisper + pyannote speaker labels."""
    model = get_whisper_model()
    diarization = diarize_audio(audio_path)
    full_audio = whisper.load_audio(str(audio_path))

    lines: list[str] = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        start_i = int(turn.start * 16000)
        end_i = int(turn.end * 16000)
        clip = whisper.pad_or_trim(full_audio[start_i:end_i])
        mel = whisper.log_mel_spectrogram(clip).to(model.device)
        result = whisper.decode(model, mel, whisper.DecodingOptions())
        text = (result.text or "").strip()
        if text:
            lines.append(f"[{turn.start:.2f}-{turn.end:.2f}] {speaker}: {text}")

    return "\n".join(lines)


def transcribe_file(input_path: str | Path, *, with_speakers: bool | None = None) -> str:
    """
    Normalize media with ffmpeg, then transcribe.

    with_speakers:
      - True  → always diarize (requires HF_TOKEN + pyannote)
      - False → plain Whisper
      - None  → diarize when HF_TOKEN is set, otherwise plain Whisper
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"File does not exist: {input_path}")

    use_speakers = _hf_token() is not None if with_speakers is None else with_speakers

    with tempfile.TemporaryDirectory(prefix="meeting_assist_") as tmp:
        wav_path = Path(tmp) / "audio.wav"
        extract_audio(input_path, wav_path)

        if use_speakers:
            return transcribe_with_speakers(wav_path)
        return transcribe_audio(wav_path)


def main(media_file: str) -> None:
    if not os.path.exists(media_file):
        print("File does not exist:", media_file)
        return

    print(f"Transcribing: {media_file}")
    transcript = transcribe_file(media_file)

    txt_file = os.path.splitext(media_file)[0] + "_transcript.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        f.write(transcript)

    print("Transcription complete. Saved to:", txt_file)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m backend.services.transcribe_mp4 <file.mp4|audio>")
    else:
        main(sys.argv[1])
