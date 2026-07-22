"""
Meeting Assist — feature tests against spec.md

Run from the project root:
    source .venv/bin/activate
    pytest tests/test_spec_features.py -v

Each failing assertion explains which spec feature broke and why.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from backend.models import ActionItem, Meeting
from backend.services import whisper_service
from tests.conftest import SAMPLE_TRANSCRIPT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def reason(feature: str, detail: str) -> str:
    return f"[{feature}] {detail}"


def assert_status(response, expected: int, feature: str, detail: str):
    assert response.status_code == expected, reason(
        feature,
        f"{detail} Expected HTTP {expected}, got {response.status_code}. "
        f"Body: {response.text[:500]}",
    )


def assert_has_keys(payload: dict, keys: list[str], feature: str, where: str):
    missing = [k for k in keys if k not in payload]
    assert not missing, reason(
        feature,
        f"{where} is missing required field(s): {missing}. "
        f"Got keys: {sorted(payload.keys())}",
    )


def iter_api_routes():
    """Yield (full_path, methods) for APIRoute entries, including included routers."""
    from fastapi.routing import APIRoute

    from backend.main import app

    def walk(routes, prefix: str = ""):
        for route in routes:
            if isinstance(route, APIRoute):
                yield prefix + route.path, set(route.methods or [])
                continue

            include_ctx = getattr(route, "include_context", None)
            original = getattr(route, "original_router", None)
            if include_ctx is not None and original is not None:
                nested_prefix = prefix + (include_ctx.prefix or "")
                yield from walk(original.routes, nested_prefix)
                continue

            if hasattr(route, "routes"):
                yield from walk(route.routes, prefix)

    yield from walk(app.router.routes)


def find_route(path: str, methods: set[str] | None = None) -> bool:
    for route_path, route_methods in iter_api_routes():
        if route_path != path:
            continue
        if methods is None:
            return True
        if methods.issubset(route_methods):
            return True
    return False


# ===========================================================================
# 1. App / backend skeleton
# ===========================================================================


class TestBackendSkeleton:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert_status(
            response,
            200,
            "Backend skeleton",
            "GET /health should confirm the FastAPI app is running.",
        )
        assert response.json().get("status") == "ok", reason(
            "Backend skeleton",
            "Health payload should be {\"status\": \"ok\"}.",
        )

    def test_meetings_router_mounted(self):
        assert find_route("/api/meetings/upload", {"POST"}), reason(
            "Backend skeleton",
            "POST /api/meetings/upload is not registered. "
            "spec.md requires the meeting router under prefix /api/meetings.",
        )
        assert find_route("/api/meetings/{meeting_id}", {"GET"}), reason(
            "Backend skeleton",
            "GET /api/meetings/{id} is not registered. "
            "spec.md requires fetching a meeting by id.",
        )

    def test_cors_middleware_present(self):
        from backend.main import app

        cors = [
            m
            for m in app.user_middleware
            if "CORSMiddleware" in getattr(m.cls, "__name__", str(m.cls))
        ]
        assert cors, reason(
            "Backend skeleton",
            "CORSMiddleware is missing. The React/HTML frontend cannot call "
            "the API from another origin without CORS headers.",
        )


# ===========================================================================
# 2. Models
# ===========================================================================


class TestModels:
    def test_meeting_model_fields(self):
        required = {"id", "title", "date", "transcript", "summary"}
        columns = set(Meeting.__table__.columns.keys())
        missing = required - columns
        assert not missing, reason(
            "Meeting model",
            f"Meeting table is missing columns required by spec.md: {sorted(missing)}. "
            f"Present: {sorted(columns)}",
        )

    def test_action_item_model_fields(self):
        required = {"id", "meeting_id", "owner", "description", "due_date"}
        columns = set(ActionItem.__table__.columns.keys())
        missing = required - columns
        assert not missing, reason(
            "ActionItem model",
            f"ActionItem table is missing columns required by spec.md: {sorted(missing)}. "
            f"Present: {sorted(columns)}",
        )

    def test_meeting_action_item_relationship(self, db_session):
        meeting = Meeting(title="Rel Test", transcript="hello")
        db_session.add(meeting)
        db_session.flush()
        item = ActionItem(
            meeting_id=meeting.id,
            owner="Alice",
            description="Send notes",
            due_date="Monday",
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(meeting)

        assert len(meeting.action_items) == 1, reason(
            "ActionItem model",
            "Meeting.action_items relationship did not load the related ActionItem. "
            "Cascade / FK wiring may be broken.",
        )
        assert meeting.action_items[0].owner == "Alice", reason(
            "ActionItem model",
            "Stored ActionItem.owner did not round-trip correctly.",
        )


# ===========================================================================
# 3. Upload + file validation
# ===========================================================================


class TestUploadAndValidation:
    def test_upload_returns_meeting_id(self, upload_audio):
        response = upload_audio()
        assert_status(
            response,
            200,
            "Upload endpoint",
            "POST /api/meetings/upload should accept an audio file and succeed.",
        )
        body = response.json()
        assert_has_keys(
            body,
            ["meeting_id", "transcript"],
            "Upload endpoint",
            "Upload response",
        )
        assert isinstance(body["meeting_id"], int) and body["meeting_id"] > 0, reason(
            "Upload endpoint",
            f"meeting_id must be a positive integer; got {body.get('meeting_id')!r}.",
        )

    def test_upload_saves_custom_title(self, upload_audio):
        response = upload_audio(title="Q3 Planning")
        assert_status(response, 200, "Upload endpoint", "Upload with title form field failed.")
        assert response.json().get("title") == "Q3 Planning", reason(
            "Upload endpoint",
            "Optional title form field was ignored. Expected title 'Q3 Planning'.",
        )

    def test_upload_rejects_unsupported_file_type(self, client):
        files = {"file": ("notes.txt", io.BytesIO(b"not audio"), "text/plain")}
        response = client.post("/api/meetings/upload", files=files)
        assert_status(
            response,
            400,
            "File validation",
            "Pipeline step 1 is Validate file. Non-audio uploads must be rejected "
            "with HTTP 400 instead of being sent to Whisper.",
        )
        detail = str(response.json().get("detail", "")).lower()
        assert "unsupported" in detail or "allowed" in detail, reason(
            "File validation",
            f"400 response should explain the unsupported type. Got: {response.json()}",
        )

    def test_upload_requires_file(self, client):
        response = client.post("/api/meetings/upload")
        assert response.status_code in {400, 422}, reason(
            "File validation",
            "POST /api/meetings/upload without a file must fail (400/422). "
            f"Got {response.status_code}.",
        )

    def test_allowed_audio_extensions(self):
        for name in ("a.mp3", "b.wav", "c.m4a", "d.webm"):
            assert whisper_service.is_allowed_audio(name), reason(
                "File validation",
                f"{name} should be an allowed audio extension per whisper_service.",
            )
        assert not whisper_service.is_allowed_audio("notes.docx"), reason(
            "File validation",
            "docx must not be treated as allowed audio.",
        )


# ===========================================================================
# 4. Whisper transcription
# ===========================================================================


class TestWhisperTranscription:
    def test_upload_runs_transcription_and_returns_text(self, upload_audio):
        response = upload_audio()
        assert_status(response, 200, "Whisper transcription", "Upload/transcription request failed.")
        transcript = response.json().get("transcript")
        assert isinstance(transcript, str) and transcript.strip(), reason(
            "Whisper transcription",
            "Upload must return a non-empty transcript string after Whisper runs. "
            f"Got: {transcript!r}",
        )
        assert transcript == SAMPLE_TRANSCRIPT, reason(
            "Whisper transcription",
            "Transcript returned by upload did not match the Whisper service output. "
            "The router may not be calling whisper_service.transcribe.",
        )

    def test_transcript_persisted_on_meeting(self, upload_audio, client):
        meeting_id = upload_audio().json()["meeting_id"]
        response = client.get(f"/api/meetings/{meeting_id}")
        assert_status(
            response,
            200,
            "Whisper transcription",
            "Could not reload meeting after upload to verify persisted transcript.",
        )
        assert response.json().get("transcript") == SAMPLE_TRANSCRIPT, reason(
            "Whisper transcription",
            "Transcript was not stored on the Meeting row (GET returned a different value). "
            "Pipeline step 4 (Store result) is incomplete for transcripts.",
        )

    def test_whisper_service_module_exists(self, project_root):
        path = project_root / "backend" / "services" / "whisper_service.py"
        assert path.is_file(), reason(
            "Whisper transcription",
            f"Missing {path}. spec.md requires backend/services/whisper_service.py.",
        )


# ===========================================================================
# 5. GET meeting
# ===========================================================================


class TestGetMeeting:
    def test_get_meeting_by_id(self, upload_audio, client):
        meeting_id = upload_audio(title="Retro").json()["meeting_id"]
        response = client.get(f"/api/meetings/{meeting_id}")
        assert_status(
            response,
            200,
            "GET meeting",
            f"GET /api/meetings/{meeting_id} should return the stored meeting.",
        )
        body = response.json()
        assert_has_keys(
            body,
            ["id", "title", "date", "transcript", "summary", "action_items"],
            "GET meeting",
            "Meeting payload",
        )
        assert body["id"] == meeting_id, reason(
            "GET meeting",
            f"Returned id {body['id']} does not match requested id {meeting_id}.",
        )
        assert body["title"] == "Retro", reason(
            "GET meeting",
            f"Title mismatch: expected 'Retro', got {body.get('title')!r}.",
        )

    def test_get_unknown_meeting_returns_404(self, client):
        response = client.get("/api/meetings/999999")
        assert_status(
            response,
            404,
            "GET meeting",
            "Unknown meeting ids must return HTTP 404.",
        )


# ===========================================================================
# 6. LLM structured notes (spec core — may still be unimplemented)
# ===========================================================================


class TestLLMStructuredNotes:
    """
    Spec pipeline step 3: Run LLM → JSON with
    {summary, key_points, decisions, action_items}.
    """

    REQUIRED_NOTE_KEYS = ["summary", "key_points", "decisions", "action_items"]

    def test_llm_service_module_exists(self, project_root):
        path = project_root / "backend" / "services" / "llm_service.py"
        assert path.is_file(), reason(
            "LLM structured notes",
            f"Missing {path}. spec.md requires an LLM service that turns a transcript "
            "into strict JSON with summary, key_points, decisions, and action_items.",
        )

    def test_upload_returns_structured_notes(self, upload_audio):
        response = upload_audio()
        assert_status(response, 200, "LLM structured notes", "Upload failed before notes could be checked.")
        body = response.json()

        notes = body.get("notes")
        if notes is None and all(k in body for k in self.REQUIRED_NOTE_KEYS):
            notes = {k: body[k] for k in self.REQUIRED_NOTE_KEYS}

        assert notes is not None, reason(
            "LLM structured notes",
            "Upload response has no structured notes. Per spec.md, after Whisper the "
            "pipeline must run an LLM and return JSON with "
            f"{self.REQUIRED_NOTE_KEYS}. Got keys: {sorted(body.keys())}.",
        )
        assert isinstance(notes, dict), reason(
            "LLM structured notes",
            f"'notes' must be an object/dict; got {type(notes).__name__}.",
        )
        assert_has_keys(
            notes,
            self.REQUIRED_NOTE_KEYS,
            "LLM structured notes",
            "Structured notes object",
        )
        assert isinstance(notes["summary"], str) and notes["summary"].strip(), reason(
            "LLM structured notes",
            "notes.summary must be a non-empty string for the result page.",
        )
        assert isinstance(notes["key_points"], list), reason(
            "LLM structured notes",
            "notes.key_points must be a list of strings (bullets on the result page).",
        )
        assert isinstance(notes["decisions"], list), reason(
            "LLM structured notes",
            "notes.decisions must be a list of strings.",
        )
        assert isinstance(notes["action_items"], list), reason(
            "LLM structured notes",
            "notes.action_items must be a list of {owner, description, due_date}.",
        )

    def test_get_meeting_includes_structured_notes(self, upload_audio, client):
        meeting_id = upload_audio().json()["meeting_id"]
        response = client.get(f"/api/meetings/{meeting_id}")
        assert_status(response, 200, "LLM structured notes", "GET meeting failed.")
        body = response.json()

        has_summary = isinstance(body.get("summary"), str) and body["summary"].strip()
        has_key_points = isinstance(body.get("key_points"), list)
        has_decisions = isinstance(body.get("decisions"), list)
        notes = body.get("notes")

        assert has_summary or (isinstance(notes, dict) and notes.get("summary")), reason(
            "LLM structured notes",
            "GET /api/meetings/{id} must return transcript + structured notes. "
            "summary is missing/empty and no notes object was found. "
            f"Got keys: {sorted(body.keys())}.",
        )
        assert has_key_points or (isinstance(notes, dict) and "key_points" in notes), reason(
            "LLM structured notes",
            "GET meeting payload is missing key_points (required for the result page bullets).",
        )
        assert has_decisions or (isinstance(notes, dict) and "decisions" in notes), reason(
            "LLM structured notes",
            "GET meeting payload is missing decisions (required for the result page).",
        )

    def test_action_items_persisted_with_owner_and_due_date(self, upload_audio, client):
        meeting_id = upload_audio().json()["meeting_id"]
        response = client.get(f"/api/meetings/{meeting_id}")
        assert_status(response, 200, "Action items", "GET meeting failed.")
        body = response.json()

        items = body.get("action_items")
        if items is None and isinstance(body.get("notes"), dict):
            items = body["notes"].get("action_items")

        assert isinstance(items, list) and len(items) > 0, reason(
            "Action items",
            "No action items were stored/returned after upload. "
            "spec.md requires action items with owner/due date when possible, "
            "persisted via the ActionItem model.",
        )

        sample = items[0]
        assert isinstance(sample, dict), reason(
            "Action items",
            f"Each action item must be an object; got {type(sample).__name__}.",
        )
        for field in ("owner", "description", "due_date"):
            assert field in sample, reason(
                "Action items",
                f"Action item is missing '{field}'. "
                "Schema must be {{owner, description, due_date}}. "
                f"Got keys: {sorted(sample.keys())}",
            )
        assert sample.get("description"), reason(
            "Action items",
            "Action item description must be a non-empty string.",
        )


# ===========================================================================
# 7. Paste text notes (spec: audio OR pasted notes)
# ===========================================================================


class TestPasteTextNotes:
    def test_paste_text_produces_structured_notes(self, client):
        """
        Accept either:
          - POST /api/meetings/upload with form field `text` / `notes`, or
          - POST /api/meetings/text (or /notes)
        """
        transcript = (
            "We agreed to delay the launch. "
            "Carol will update the roadmap by Thursday."
        )

        attempts = [
            ("POST", "/api/meetings/upload", {"data": {"text": transcript}}),
            ("POST", "/api/meetings/upload", {"data": {"notes": transcript}}),
            ("POST", "/api/meetings/text", {"json": {"text": transcript}}),
            ("POST", "/api/meetings/notes", {"json": {"text": transcript}}),
        ]

        last_status = None
        last_body = None
        for method, path, kwargs in attempts:
            if method == "POST":
                response = client.post(path, **kwargs)
            else:
                response = client.request(method, path, **kwargs)
            last_status = response.status_code
            if response.status_code == 200:
                last_body = response.json()
                break

        assert last_status == 200 and last_body is not None, reason(
            "Paste text notes",
            "Could not submit pasted meeting notes. spec.md goal is "
            "'Upload a meeting audio file (or pasted notes)'. "
            "Tried upload with form fields text/notes and endpoints "
            "/api/meetings/text and /api/meetings/notes. "
            f"Last status: {last_status}.",
        )

        notes = last_body.get("notes") or last_body
        for key in ("summary", "key_points", "decisions", "action_items"):
            assert key in notes or key in last_body, reason(
                "Paste text notes",
                f"Pasted-notes flow must still return structured field '{key}' "
                "(skip Whisper, run LLM). "
                f"Got keys: {sorted(last_body.keys())}",
            )


# ===========================================================================
# 8. Frontend (spec section 5)
# ===========================================================================


class TestFrontend:
    def _frontend_roots(self, project_root: Path) -> list[Path]:
        candidates = [
            project_root / "frontend",
            project_root / "web",
            project_root / "client",
        ]
        roots = [p for p in candidates if p.is_dir()]
        if (project_root / "index.html").is_file():
            roots.append(project_root)
        return roots

    def test_frontend_project_exists(self, project_root):
        assert self._frontend_roots(project_root), reason(
            "Frontend",
            "No frontend found. spec.md requires a React+Vite app or a minimal "
            "HTML/JS page with upload + result views. Expected one of: "
            "frontend/, web/, client/, or index.html at the repo root.",
        )

    def test_frontend_has_upload_and_result_ui(self, project_root):
        roots = self._frontend_roots(project_root)
        assert roots, reason(
            "Frontend",
            "No frontend found, so upload/result UI cannot be verified. "
            "Add frontend/ (React+Vite) or a root index.html first.",
        )

        text_blobs: list[str] = []
        for root in roots:
            patterns = ("*.tsx", "*.jsx", "*.ts", "*.js", "*.html", "*.vue")
            for pattern in patterns:
                for path in root.rglob(pattern):
                    if "node_modules" in path.parts or ".venv" in path.parts:
                        continue
                    try:
                        text_blobs.append(path.read_text(encoding="utf-8", errors="ignore"))
                    except OSError:
                        continue

        combined = "\n".join(text_blobs).lower()
        assert combined.strip(), reason(
            "Frontend",
            "Frontend directory exists but no UI source files were readable.",
        )

        upload_signals = (
            'type="file"',
            "type='file'",
            "upload",
            "formdata",
            "/api/meetings/upload",
        )
        assert any(s in combined for s in upload_signals), reason(
            "Frontend",
            "Upload page is missing. UI must let the user select an audio file "
            "(or paste text) and POST to /api/meetings/upload.",
        )

        result_signals = ("summary", "key_points", "key points", "decisions", "action")
        hits = [s for s in result_signals if s in combined]
        assert len(hits) >= 2, reason(
            "Frontend",
            "Result page looks incomplete. It should render summary, key points, "
            "decisions, and action items. "
            f"Only found signals: {hits or 'none'}.",
        )


# ===========================================================================
# 9. Stretch goals from spec.md
# ===========================================================================


class TestStretchHistory:
    def test_list_meetings_endpoint(self, upload_audio, client):
        upload_audio(title="Meeting A")
        upload_audio(title="Meeting B")

        for path in ("/api/meetings", "/api/meetings/", "/api/meetings/list"):
            response = client.get(path)
            if response.status_code == 200:
                payload = response.json()
                meetings = payload if isinstance(payload, list) else payload.get("meetings")
                assert isinstance(meetings, list) and len(meetings) >= 2, reason(
                    "History (stretch)",
                    f"{path} returned 200 but not a list of stored meetings. "
                    f"Got: {payload!r}",
                )
                return

        assert False, reason(
            "History (stretch)",
            "No meetings list endpoint found. Stretch goal: store meetings and "
            "show a Meetings list page — needs GET /api/meetings (or /list) "
            "returning previously uploaded meetings.",
        )


class TestStretchSearch:
    def test_search_transcripts(self, upload_audio, client):
        upload_audio(title="Searchable")
        needle = "beta"

        for path in (
            f"/api/meetings/search?q={needle}",
            f"/api/meetings?search={needle}",
            f"/api/meetings?q={needle}",
        ):
            response = client.get(path)
            if response.status_code == 200:
                payload = response.json()
                meetings = payload if isinstance(payload, list) else payload.get("meetings")
                assert isinstance(meetings, list), reason(
                    "Search (stretch)",
                    f"{path} should return matching meetings as a list. Got: {payload!r}",
                )
                assert meetings, reason(
                    "Search (stretch)",
                    f"Search for '{needle}' returned no meetings even though a "
                    "transcript containing that term was uploaded.",
                )
                return

        assert False, reason(
            "Search (stretch)",
            "No transcript search endpoint found. Stretch goal: simple text search "
            "over transcripts (e.g. GET /api/meetings/search?q=...).",
        )


class TestStretchExports:
    def test_export_markdown_or_json(self, upload_audio, client):
        meeting_id = upload_audio().json()["meeting_id"]

        for path, expect_json in (
            (f"/api/meetings/{meeting_id}/export?format=json", True),
            (f"/api/meetings/{meeting_id}/export.json", True),
            (f"/api/meetings/{meeting_id}/export?format=markdown", False),
            (f"/api/meetings/{meeting_id}/export.md", False),
        ):
            response = client.get(path)
            if response.status_code != 200:
                continue
            if expect_json:
                try:
                    json.loads(response.text)
                except json.JSONDecodeError as exc:
                    assert False, reason(
                        "Exports (stretch)",
                        f"{path} returned 200 but body is not valid JSON: {exc}",
                    )
            else:
                assert response.text.strip(), reason(
                    "Exports (stretch)",
                    f"{path} returned an empty Markdown export.",
                )
            return

        assert False, reason(
            "Exports (stretch)",
            "No export endpoint found. Stretch goal: download Markdown minutes or JSON "
            f"(e.g. GET /api/meetings/{{id}}/export?format=markdown|json). "
            f"Tried for meeting_id={meeting_id}.",
        )


class TestStretchTags:
    def test_auto_extracted_topics(self, upload_audio, client):
        meeting_id = upload_audio().json()["meeting_id"]
        response = client.get(f"/api/meetings/{meeting_id}")
        assert_status(response, 200, "Tags (stretch)", "GET meeting failed.")
        body = response.json()

        tags = body.get("tags") or body.get("topics")
        if tags is None and isinstance(body.get("notes"), dict):
            tags = body["notes"].get("tags") or body["notes"].get("topics")

        assert isinstance(tags, list) and len(tags) > 0, reason(
            "Tags (stretch)",
            "No auto-extracted topics/tags on the meeting. Stretch goal: LLM should "
            "return topics (e.g. tags or topics list) for filtering/display. "
            f"Got keys: {sorted(body.keys())}.",
        )


# ===========================================================================
# Optional: real Whisper smoke (skipped by default — slow / needs ffmpeg)
# ===========================================================================


@pytest.mark.integration
@pytest.mark.skip(reason="Slow real-Whisper smoke test; run with: pytest -m integration --runxfail")
def test_real_whisper_transcribe_smoke(tmp_path):
    """Un-skip manually if you want to verify the actual Whisper model."""
    import subprocess

    wav = tmp_path / "speech.wav"
    aiff = tmp_path / "speech.aiff"
    subprocess.run(
        ["say", "-o", str(aiff), "Shipping the beta on Friday."],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(aiff), "-ar", "16000", "-ac", "1", str(wav)],
        check=True,
        capture_output=True,
    )
    text = whisper_service.transcribe(wav)
    assert text and text.strip(), reason(
        "Whisper transcription",
        "Real Whisper returned an empty transcript for spoken audio.",
    )
