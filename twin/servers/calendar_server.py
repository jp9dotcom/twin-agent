from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer

from twin.backends.base import CalendarBackend, CalendarEvent
from twin.backends.fake import FakeBackend
from twin.policy.gate import classify

_DEFAULT_TZ = ZoneInfo("Asia/Kolkata")


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=_DEFAULT_TZ)
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_DEFAULT_TZ)
    return parsed.astimezone(_DEFAULT_TZ)


def _event_to_dict(event: CalendarEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "title": event.title,
        "start": event.start.isoformat(),
        "end": event.end.isoformat(),
        "attendees": list(event.attendees),
        "description": event.description,
        "organizer": event.organizer,
    }


def _error(code: str, hint: str, *, nearby_event_ids: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"error": code, "hint": hint}
    if nearby_event_ids:
        result["nearby_event_ids"] = nearby_event_ids
    result.update(extra)
    return result


def _build_backend() -> CalendarBackend:
    backend_name = os.getenv("TWIN_CALENDAR_BACKEND", "fake")
    if backend_name == "fake":
        return FakeBackend()
    if backend_name == "google":
        raise NotImplementedError("Google Calendar backend is not implemented in phase 1.")
    raise ValueError(f"Unsupported calendar backend '{backend_name}'. Use 'fake' or 'google'.")


def _overlapping_ids(backend: CalendarBackend, event_id: str, new_start: datetime, new_end: datetime) -> list[str]:
    overlaps = []
    for event in backend.list_events(new_start, new_end):
        if event.id != event_id:
            overlaps.append(event.id)
    return overlaps


def build_calendar_server(backend: CalendarBackend | None = None) -> MCPServer:
    """Create the calendar MCP server with the requested backend."""
    selected_backend = backend or _build_backend()
    mcp = MCPServer(name="twin-calendar", version="0.1.0", description="Calendar operations for Twin.")

    @mcp.tool(name="list_events", structured_output=True)
    def list_events(start: str, end: str) -> dict[str, Any]:
        """List all calendar events overlapping a time window.

        Args:
            start: ISO 8601 datetime, for example "2026-10-27T00:00:00+05:30".
            end: ISO 8601 datetime, for example "2026-10-27T23:59:00+05:30".

        Returns:
            A dictionary like {"events": [{...}], "count": 3}. Errors are returned as
            {"error": "invalid_time_range", "hint": "..."} when the window is malformed.
        """
        try:
            start_dt = _parse_datetime(start)
            end_dt = _parse_datetime(end)
        except ValueError:
            return _error("invalid_time_range", "start and end must be ISO 8601 datetimes.")
        if end_dt <= start_dt:
            return _error("invalid_time_range", "end must be after start.")
        events = selected_backend.list_events(start_dt, end_dt)
        return {"events": [_event_to_dict(item) for item in events], "count": len(events)}

    mcp.list_events = list_events

    @mcp.tool(name="get_event", structured_output=True)
    def get_event(event_id: str) -> dict[str, Any]:
        """Fetch one calendar event by id.

        Args:
            event_id: Event identifier, for example "evt-1".

        Returns:
            A dictionary with the event payload or a structured error like
            {"error": "event_not_found", "hint": "..."}.
        """
        event = selected_backend.get_event(event_id)
        if event is None:
            return _error("event_not_found", f"No event found for id '{event_id}'.")
        return {"event": _event_to_dict(event)}

    mcp.get_event = get_event

    @mcp.tool(name="move_event", structured_output=True)
    def move_event(event_id: str, new_start: str | datetime, new_end: str | datetime, dry_run: bool = True) -> dict[str, Any]:
        """Move an event to a new time window.

        Args:
            event_id: The event identifier, for example "evt-1".
            new_start: ISO 8601 datetime for the new start, for example "2026-10-27T09:00:00+05:30".
            new_end: ISO 8601 datetime for the new end, for example "2026-10-27T10:00:00+05:30".
            dry_run: If true, validate and preview without mutating state.

        Returns:
            A dictionary like {"would_do": "...", "affected_attendees": [...], "inverse": {...}, "warnings": [...]}
            or {"would_do": "...", "affected_attendees": [...], "inverse": {...}, "applied": true} when applied.
        """
        try:
            new_start_dt = _parse_datetime(new_start)
            new_end_dt = _parse_datetime(new_end)
        except ValueError:
            return _error("invalid_time_range", "new_start and new_end must be ISO 8601 datetimes.")
        if new_end_dt <= new_start_dt:
            return _error("invalid_time_range", "new_end must be after new_start.")

        existing = selected_backend.get_event(event_id)
        if existing is None:
            return _error("event_not_found", f"No event found for id '{event_id}'.")

        overlaps = _overlapping_ids(selected_backend, event_id, new_start_dt, new_end_dt)
        decision = classify(
            "move_event",
            {"event_id": event_id, "new_start": new_start_dt.isoformat(), "new_end": new_end_dt.isoformat()},
            {"attendee_count": len(existing.attendees)},
        )
        warning_list = []
        if overlaps:
            warning_list.append(f"Event overlaps with {', '.join(overlaps)}.")

        payload: dict[str, Any] = {
            "would_do": (
                f"Move '{existing.title}' from {existing.start.isoformat()} to {new_start_dt.isoformat()} - "
                f"{new_end_dt.isoformat()}"
            ),
            "affected_attendees": list(existing.attendees),
            "inverse": {
                "tool": "move_event",
                "args": {
                    "event_id": event_id,
                    "new_start": existing.start.isoformat(),
                    "new_end": existing.end.isoformat(),
                },
            },
            "warnings": warning_list,
            "risk": decision.risk,
            "needs_approval": decision.needs_approval,
            "reasons": decision.reasons,
        }

        if dry_run:
            return payload

        updated = selected_backend.move_event(event_id, new_start_dt, new_end_dt)
        result = dict(payload)
        result["applied"] = True
        result["would_do"] = (
            f"Moved '{updated.title}' from {existing.start.isoformat()} to {updated.start.isoformat()} - "
            f"{updated.end.isoformat()}"
        )
        result["affected_attendees"] = list(updated.attendees)
        return result

    mcp.move_event = move_event

    @mcp.tool(name="cancel_event", structured_output=True)
    def cancel_event(event_id: str, dry_run: bool = True) -> dict[str, Any]:
        """Cancel an event without deleting it from the logs until applied.

        Args:
            event_id: Event identifier, for example "evt-1".
            dry_run: If true, do not mutate the backend; return the planned effect.

        Returns:
            A dictionary like {"would_do": "...", "affected_attendees": [...], "inverse": {...}}.
            When applied, the payload also includes {"applied": true}.
        """
        existing = selected_backend.get_event(event_id)
        if existing is None:
            return _error("event_not_found", f"No event found for id '{event_id}'.")

        decision = classify(
            "cancel_event",
            {"event_id": event_id},
            {"attendee_count": len(existing.attendees)},
        )
        payload: dict[str, Any] = {
            "would_do": f"Cancel event '{existing.title}' scheduled from {existing.start.isoformat()} to {existing.end.isoformat()}",
            "affected_attendees": list(existing.attendees),
            "inverse": {
                "tool": "move_event",
                "args": {
                    "event_id": event_id,
                    "new_start": existing.start.isoformat(),
                    "new_end": existing.end.isoformat(),
                },
            },
            "risk": decision.risk,
            "needs_approval": decision.needs_approval,
            "reasons": decision.reasons,
        }
        if dry_run:
            return payload
        cancelled = selected_backend.cancel_event(event_id)
        result = dict(payload)
        result["applied"] = True
        result["would_do"] = f"Cancelled event '{cancelled.title}' scheduled from {cancelled.start.isoformat()} to {cancelled.end.isoformat()}"
        return result

    mcp.cancel_event = cancel_event

    return mcp


if __name__ == "__main__":
    build_calendar_server().run(transport="stdio")
