from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

RISK_ORDER = {
    "read": 0,
    "reversible": 1,
    "irreversible": 2,
    "irreversible-equivalent": 3,
}


@dataclass(frozen=True)
class GateDecision:
    """Deterministic decision for a tool call risk assessment."""

    risk: str
    needs_approval: bool
    reasons: list[str] = field(default_factory=list)


def _load_map() -> dict[str, Any]:
    risk_file = Path(__file__).with_name("risk_map.yaml")
    with risk_file.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _compare(actual: Any, op: str, expected: Any) -> bool:
    if actual is None:
        return False
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "gt":
        return actual > expected
    if op == "ge":
        return actual >= expected
    if op == "lt":
        return actual < expected
    if op == "le":
        return actual <= expected
    return False


def _max_risk(current: str, candidate: str) -> str:
    return candidate if RISK_ORDER.get(candidate, -1) > RISK_ORDER.get(current, -1) else current


def classify(tool: str, args: dict[str, Any], event_context: dict[str, Any]) -> GateDecision:
    """Classify tool risk using the deterministic risk map."""
    risk_map = _load_map().get("tools", {})
    tool_rule = risk_map.get(tool) or risk_map.get("default")

    if tool_rule is None:
        return GateDecision(
            risk="irreversible-equivalent",
            needs_approval=True,
            reasons=[f"Unknown tool '{tool}' is denied by policy."],
        )

    effective_risk = str(tool_rule.get("base", "read"))
    reasons: list[str] = []

    for escalation in tool_rule.get("escalate_if", []):
        field = str(escalation.get("field", ""))
        op = str(escalation.get("op", "eq"))
        value = escalation.get("value")
        actual = event_context.get(field)
        if actual is None and field in args:
            actual = args.get(field)
        if _compare(actual, op, value):
            effective_risk = _max_risk(effective_risk, str(escalation.get("to", effective_risk)))
            reasons.append(str(escalation.get("reason", f"Escalation for {field} matched.")))

    if tool not in risk_map:
        return GateDecision(
            risk="irreversible-equivalent",
            needs_approval=True,
            reasons=[f"Unknown tool '{tool}' is denied by policy."],
        )

    return GateDecision(
        risk=effective_risk,
        needs_approval=RISK_ORDER.get(effective_risk, 0) >= RISK_ORDER.get("irreversible", 0),
        reasons=reasons,
    )
