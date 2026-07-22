from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ActionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_id: int
    owner: str | None = None
    description: str
    due_date: str | None = None


class ActionItemNote(BaseModel):
    owner: str | None = None
    description: str
    due_date: str | None = None


class StructuredNotes(BaseModel):
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[ActionItemNote] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    date: datetime
    transcript: str | None = None
    summary: str | None = None
    key_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    action_items: list[ActionItemOut] = Field(default_factory=list)

    @classmethod
    def from_meeting(cls, meeting) -> "MeetingOut":
        tags = list(meeting.tags or [])
        return cls(
            id=meeting.id,
            title=meeting.title,
            date=meeting.date,
            transcript=meeting.transcript,
            summary=meeting.summary,
            key_points=list(meeting.key_points or []),
            decisions=list(meeting.decisions or []),
            tags=tags,
            topics=tags,
            action_items=meeting.action_items or [],
        )


class MeetingListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    date: datetime
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)


class UploadResponse(BaseModel):
    meeting_id: int
    title: str
    transcript: str
    notes: StructuredNotes


class TextNotesRequest(BaseModel):
    text: str = Field(min_length=1)
    title: str | None = None
