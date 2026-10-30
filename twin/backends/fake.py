from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from twin.backends.base import CalendarBackend, CalendarEvent


class FakeBackend:
    """SQLite-backed calendar backend for development and tests."""

    def __init__(self, db_path: str | Path = "calendar.db") -> None:
        self.db_path = str(db_path)
        self._ensure_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    start TEXT NOT NULL,
                    end TEXT NOT NULL,
                    attendees TEXT,
                    description TEXT,
                    organizer TEXT
                )
                """
            )

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        return value.astimezone(ZoneInfo("Asia/Kolkata"))

    def _event_from_row(self, row: sqlite3.Row) -> CalendarEvent:
        start = datetime.fromisoformat(row["start"]) if row["start"] else datetime.now(tz=ZoneInfo("Asia/Kolkata"))
        end = datetime.fromisoformat(row["end"]) if row["end"] else datetime.now(tz=ZoneInfo("Asia/Kolkata"))
        attendees_raw = json.loads(row["attendees"]) if row["attendees"] else []
        return CalendarEvent(
            id=row["id"],
            title=row["title"],
            start=start,
            end=end,
            attendees=list(attendees_raw),
            description=row["description"] or "",
            organizer=row["organizer"] or "",
        )

    def seed_week(self) -> list[CalendarEvent]:
        """Populate the database with a realistic weekly sample set."""
        templates = [
            {
                "id": "evt-1",
                "title": "Team sync",
                "start": datetime(2026, 10, 26, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
                "end": datetime(2026, 10, 26, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
                "attendees": ["aisha@example.com", "ben@example.com", "carl@example.com", "dana@example.com"],
                "description": "Weekly team coordination meeting.",
                "organizer": "aisha@example.com",
            },
            {
                "id": "evt-2",
                "title": "Deep work block",
                "start": datetime(2026, 10, 27, 11, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
                "end": datetime(2026, 10, 27, 13, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
                "attendees": ["ben@example.com"],
                "description": "Focus time for roadmap planning.",
                "organizer": "ben@example.com",
            },
            {
                "id": "evt-3",
                "title": "Client review",
                "start": datetime(2026, 10, 28, 15, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
                "end": datetime(2026, 10, 28, 17, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
                "attendees": ["nina@example.com", "omar@example.com", "pete@example.com", "quinn@example.com"],
                "description": "Quarterly review with product stakeholders.",
                "organizer": "nina@example.com",
            },
            {
                "id": "evt-4",
                "title": "1:1 mentor check-in",
                "start": datetime(2026, 10, 29, 10, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
                "end": datetime(2026, 10, 29, 11, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
                "attendees": ["ravi@example.com", "sana@example.com"],
                "description": "Career coaching and planning.",
                "organizer": "ravi@example.com",
            },
            {
                "id": "evt-5",
                "title": "Ops planning",
                "start": datetime(2026, 10, 30, 14, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
                "end": datetime(2026, 10, 30, 15, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
                "attendees": ["tina@example.com", "umar@example.com", "vijay@example.com", "willa@example.com", "xavier@example.com"],
                "description": "Weekly operations planning.",
                "organizer": "tina@example.com",
            },
            {
                "id": "evt-6",
                "title": "Lunch with family",
                "start": datetime(2026, 10, 31, 12, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
                "end": datetime(2026, 10, 31, 13, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
                "attendees": ["maya@example.com", "zoe@example.com"],
                "description": "Personal lunch and catch-up.",
                "organizer": "maya@example.com",
            },
            {
                "id": "evt-7",
                "title": "Project handoff",
                "start": datetime(2026, 11, 1, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
                "end": datetime(2026, 11, 1, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
                "attendees": ["aaron@example.com", "bella@example.com", "charlie@example.com", "daisy@example.com"],
                "description": "Project transition review.",
                "organizer": "aaron@example.com",
            },
        ]

        with self._connect() as connection:
            connection.execute("DELETE FROM events")
            for item in templates:
                connection.execute(
                    """
                    INSERT INTO events (id, title, start, end, attendees, description, organizer)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"],
                        item["title"],
                        item["start"].isoformat(),
                        item["end"].isoformat(),
                        json.dumps(item["attendees"]),
                        item["description"],
                        item["organizer"],
                    ),
                )

        return [self.get_event(item["id"]) for item in templates]

    def list_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        """Return events whose time ranges overlap the requested window."""
        start = self._normalize_datetime(start)
        end = self._normalize_datetime(end)
        if end <= start:
            raise ValueError("end must be after start")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM events
                WHERE start < ? AND end > ?
                ORDER BY start ASC
                """,
                (end.isoformat(), start.isoformat()),
            ).fetchall()
        return [self._event_from_row(row) for row in rows]

    def get_event(self, event_id: str) -> CalendarEvent | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            return None
        return self._event_from_row(row)

    def move_event(self, event_id: str, new_start: datetime, new_end: datetime) -> CalendarEvent:
        new_start = self._normalize_datetime(new_start)
        new_end = self._normalize_datetime(new_end)
        if new_end <= new_start:
            raise ValueError("new_end must be greater than new_start")
        event = self.get_event(event_id)
        if event is None:
            raise KeyError(f"Unknown event id: {event_id}")
        with self._connect() as connection:
            connection.execute(
                "UPDATE events SET start = ?, end = ? WHERE id = ?",
                (new_start.isoformat(), new_end.isoformat(), event_id),
            )
        updated = self.get_event(event_id)
        if updated is None:
            raise RuntimeError(f"Unable to find updated event {event_id}")
        return updated

    def cancel_event(self, event_id: str) -> CalendarEvent | None:
        event = self.get_event(event_id)
        if event is None:
            return None
        with self._connect() as connection:
            connection.execute("DELETE FROM events WHERE id = ?", (event_id,))
        return event


CalendarBackend.register(FakeBackend)
