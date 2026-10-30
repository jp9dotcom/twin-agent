import json

from twin.store.actions import (
    get_inverse_chain,
    mark_applied,
    mark_failed,
    record_action,
)


def test_record_action_is_idempotent_and_status_helpers_work(tmp_path):
    db_path = tmp_path / "actions.db"
    action = record_action(
        db_path=str(db_path),
        tool="move_event",
        args={"event_id": "abc", "new_start": "2026-10-27T09:00:00+05:30"},
        inverse={"tool": "move_event", "args": {"event_id": "abc", "new_start": "2026-10-26T09:00:00+05:30"}},
        idempotency_key="run-1",
    )
    duplicate = record_action(
        db_path=str(db_path),
        tool="move_event",
        args={"event_id": "abc", "new_start": "2026-10-27T10:00:00+05:30"},
        inverse={"tool": "move_event", "args": {"event_id": "abc", "new_start": "2026-10-26T10:00:00+05:30"}},
        idempotency_key="run-1",
    )

    assert action["id"] == duplicate["id"]
    assert json.loads(action["args_json"])["event_id"] == "abc"

    mark_applied(db_path=str(db_path), action_id=action["id"])
    failed = mark_failed(db_path=str(db_path), action_id=action["id"], reason="bad input")
    assert failed["status"] == "failed"

    chain = get_inverse_chain(db_path=str(db_path), run_id=action["id"])
    assert chain and isinstance(chain, list)
    assert chain[0]["tool"] == "move_event"
