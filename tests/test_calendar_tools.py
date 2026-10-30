from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from twin.backends.fake import FakeBackend
from twin.servers.calendar_server import build_calendar_server


def test_dry_run_does_not_mutate_and_invalid_inputs_are_structured(tmp_path):
    backend = FakeBackend(db_path=str(tmp_path / "calendar.db"))
    backend.seed_week()
    server = build_calendar_server(backend)

    event = backend.list_events(
        datetime(2026, 10, 26, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        datetime(2026, 10, 26, 18, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
    )[0]
    original = backend.get_event(event.id)

    new_start = original.start + timedelta(hours=1)
    new_end = original.end + timedelta(hours=1)
    dry = server.move_event(event.id, new_start, new_end, dry_run=True)
    assert dry["would_do"]
    assert backend.get_event(event.id).start == original.start

    bad = server.move_event(event.id, original.end + timedelta(minutes=30), original.start)
    assert bad["error"] == "invalid_time_range"
    assert bad["hint"]


def test_apply_then_inverse_restores_original_state(tmp_path):
    backend = FakeBackend(db_path=str(tmp_path / "calendar.db"))
    backend.seed_week()
    server = build_calendar_server(backend)

    event = backend.list_events(
        datetime(2026, 10, 27, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        datetime(2026, 10, 27, 18, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
    )[0]
    before = backend.get_event(event.id)
    after_start = before.start + timedelta(hours=2)
    after_end = before.end + timedelta(hours=2)

    changed = server.move_event(event.id, after_start, after_end, dry_run=False)
    assert changed["applied"] is True
    assert backend.get_event(event.id).start == after_start

    inverse = changed["inverse"]
    restored = getattr(server, inverse["tool"])(**inverse["args"], dry_run=False)
    assert restored["applied"] is True
    assert backend.get_event(event.id).start == before.start


def test_cancel_event_dry_run_and_apply(tmp_path):
    backend = FakeBackend(db_path=str(tmp_path / "calendar.db"))
    backend.seed_week()
    server = build_calendar_server(backend)

    event = backend.list_events(
        datetime(2026, 10, 28, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
        datetime(2026, 10, 28, 18, 0, tzinfo=ZoneInfo("Asia/Kolkata")),
    )[0]

    dry = server.cancel_event(event.id, dry_run=True)
    assert dry["would_do"]
    assert backend.get_event(event.id) is not None

    applied = server.cancel_event(event.id, dry_run=False)
    assert applied["applied"] is True
    assert backend.get_event(event.id) is None
