from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from twin.backends.fake import FakeBackend


def test_seed_creates_realistic_week_and_attendees(tmp_path):
    db_path = tmp_path / "calendar.db"
    backend = FakeBackend(db_path=str(db_path))
    backend.seed_week()

    events = backend.list_events(
        datetime(2026, 10, 26, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        datetime(2026, 11, 1, 18, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
    )
    assert events
    assert any(len(event.attendees) >= 3 for event in events)
    assert all(event.start.tzinfo is not None for event in events)
    assert all(event.end.tzinfo is not None for event in events)


def test_move_and_cancel_event(tmp_path):
    db_path = tmp_path / "calendar.db"
    backend = FakeBackend(db_path=str(db_path))
    backend.seed_week()

    event = backend.list_events(
        datetime(2026, 10, 26, 9, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        datetime(2026, 10, 26, 18, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
    )[0]
    original = backend.get_event(event.id)
    new_start = original.start + timedelta(hours=2)
    new_end = original.end + timedelta(hours=2)

    moved = backend.move_event(event.id, new_start, new_end)
    assert moved.start == new_start
    assert moved.end == new_end

    cancelled = backend.cancel_event(event.id)
    assert cancelled is not None
    assert backend.get_event(event.id) is None
