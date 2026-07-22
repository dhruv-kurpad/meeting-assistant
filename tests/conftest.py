"""Shared fixtures for Meeting Assist feature tests."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend.main import app


SAMPLE_TRANSCRIPT = (
    "Hello team. We decided to ship the beta on Friday. "
    "Alice will send the notes by Monday. "
    "Bob owns the launch checklist."
)


@pytest.fixture()
def db_session():
    """Isolated in-memory SQLite for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session, monkeypatch, tmp_path):
    """API client with test DB, temp uploads, and mocked Whisper."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr("backend.routers.meeting.UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(
        "backend.services.whisper_service.transcribe",
        lambda _path: SAMPLE_TRANSCRIPT,
    )

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture()
def tiny_wav_bytes() -> bytes:
    """Minimal valid-ish WAV header + silence (Whisper is mocked in client tests)."""
    # 44-byte WAV header for 1 sample of silence is enough for multipart upload.
    return (
        b"RIFF$\x00\x00\x00WAVEfmt "
        b"\x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x40\x1f\x00\x00\x80\x3e\x00\x00"
        b"\x02\x00\x10\x00data\x00\x00\x00\x00"
    )


@pytest.fixture()
def upload_audio(client, tiny_wav_bytes):
    """Helper: POST an audio file and return the JSON body."""

    def _upload(filename: str = "standup.wav", title: str | None = "Weekly Standup"):
        files = {"file": (filename, io.BytesIO(tiny_wav_bytes), "audio/wav")}
        data = {"title": title} if title is not None else None
        return client.post("/api/meetings/upload", files=files, data=data)

    return _upload


@pytest.fixture()
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]
