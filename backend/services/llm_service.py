from __future__ import annotations

import json
import os
import re
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

PROMPT = """You are a meeting notes assistant.
Given the transcript, return STRICT JSON only (no markdown fences) with this schema:
{{
  "summary": "string — 2-4 sentence overview",
  "key_points": ["string", "..."],
  "decisions": ["string", "..."],
  "action_items": [
    {{"owner": "string or null", "description": "string", "due_date": "string or null"}}
  ],
  "topics": ["string", "..."]
}}

Rules:
- Use null for owner/due_date when unknown (do not invent people or dates).
- topics should be short tags (1-3 words) describing themes.
- If something is absent, use an empty list.

Transcript:
{transcript}
"""


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("LLM response did not contain JSON.") from None
        return json.loads(match.group(0))


def _normalize(notes: dict[str, Any]) -> dict[str, Any]:
    action_items: list[dict[str, Any]] = []
    for raw in notes.get("action_items") or []:
        if not isinstance(raw, dict):
            continue
        description = (raw.get("description") or "").strip()
        if not description:
            continue
        owner = raw.get("owner")
        due_date = raw.get("due_date")
        action_items.append(
            {
                "owner": (str(owner).strip() if owner not in (None, "") else None),
                "description": description,
                "due_date": (str(due_date).strip() if due_date not in (None, "") else None),
            }
        )

    def as_str_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    summary = notes.get("summary")
    return {
        "summary": (str(summary).strip() if summary else ""),
        "key_points": as_str_list(notes.get("key_points")),
        "decisions": as_str_list(notes.get("decisions")),
        "action_items": action_items,
        "topics": as_str_list(notes.get("topics") or notes.get("tags")),
    }


def summarize(transcript: str) -> dict[str, Any]:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is missing. Add it to your .env file."
        )

    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5").strip()
    client = Anthropic(api_key=api_key)
    prompt = PROMPT.format(transcript=transcript)

    message = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    chunks: list[str] = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            chunks.append(block.text)
    raw_text = "".join(chunks).strip()
    if not raw_text:
        raise ValueError("Claude returned an empty response.")

    return _normalize(_extract_json(raw_text))
