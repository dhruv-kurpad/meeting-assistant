from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ActionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    owner: str | None = None
    description: str
    due_date: str | None = None


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    date: datetime
    transcript: str | None = None
    summary: str | None = None
    action_items: list[ActionItemOut] = []


class UploadResponse(BaseModel):
    meeting_id: int
    title: str
    transcript: str
