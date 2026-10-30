from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict


class CalendarEvent(BaseModel):
    """Canonical event model for calendar data."""

    model_config = ConfigDict(extra="ignore")

    id: str
    title: str
    start: datetime
    end: datetime
    attendees: list[str] = []
    description: str = ""
    organizer: str = ""


@runtime_checkable
class CalendarBackend(Protocol):
    """Calendar backend contract for reading and mutating events."""

    def list_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        """Return all events overlapping the given time range."""

    def get_event(self, event_id: str) -> CalendarEvent | None:
        """Return a single event by id or None when absent."""

    def move_event(self, event_id: str, new_start: datetime, new_end: datetime) -> CalendarEvent:
        """Move an event to a new time range and return the updated event."""

    def cancel_event(self, event_id: str) -> CalendarEvent | None:
        """Remove an event and return the deleted event payload."""
