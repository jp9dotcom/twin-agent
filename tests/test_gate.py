from twin.policy.gate import classify


def test_gate_escalates_attendee_moves_and_fails_closed_for_unknown_tools():
    decision = classify(
        "move_event",
        {"new_start": "2026-10-27T09:00:00+05:30", "new_end": "2026-10-27T10:00:00+05:30"},
        {"attendee_count": 4},
    )
    assert decision.risk == "irreversible-equivalent"
    assert decision.needs_approval is True
    assert decision.reasons

    unknown = classify("unknown_tool", {}, {})
    assert unknown.needs_approval is True
    assert unknown.risk in {"irreversible", "irreversible-equivalent"}


def test_gate_reads_are_low_risk():
    decision = classify("list_events", {"start": "2026-10-27T00:00:00+05:30", "end": "2026-10-27T23:59:00+05:30"}, {})
    assert decision.risk == "read"
    assert decision.needs_approval is False
