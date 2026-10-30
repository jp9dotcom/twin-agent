from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


def _connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_schema(db_path: str | Path) -> None:
    with _connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool TEXT NOT NULL,
                args_json TEXT NOT NULL,
                inverse_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','applied','rolled_back','failed')),
                idempotency_key TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def record_action(
    *,
    db_path: str | Path,
    tool: str,
    args: dict[str, Any],
    inverse: dict[str, Any],
    idempotency_key: str,
    status: str = "planned",
) -> dict[str, Any]:
    """Insert an action row if the idempotency key is new; otherwise return the existing row."""
    _ensure_schema(db_path)
    payload = {"tool": tool, "args_json": json.dumps(args, sort_keys=True), "inverse_json": json.dumps(inverse, sort_keys=True)}
    with _connect(db_path) as connection:
        existing = connection.execute(
            "SELECT * FROM actions WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if existing is not None:
            return dict(existing)
        cursor = connection.execute(
            """
            INSERT INTO actions (tool, args_json, inverse_json, status, idempotency_key)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tool, payload["args_json"], payload["inverse_json"], status, idempotency_key),
        )
        row = connection.execute("SELECT * FROM actions WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)


def mark_applied(*, db_path: str | Path, action_id: int) -> dict[str, Any]:
    """Update an action status to applied and return the row."""
    _ensure_schema(db_path)
    with _connect(db_path) as connection:
        connection.execute("UPDATE actions SET status = 'applied' WHERE id = ?", (action_id,))
        row = connection.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    return dict(row)


def mark_failed(*, db_path: str | Path, action_id: int, reason: str | None = None) -> dict[str, Any]:
    """Update an action status to failed and return the row."""
    _ensure_schema(db_path)
    del reason
    with _connect(db_path) as connection:
        connection.execute("UPDATE actions SET status = 'failed' WHERE id = ?", (action_id,))
        row = connection.execute("SELECT * FROM actions WHERE id = ?", (action_id,)).fetchone()
    return dict(row)


def get_inverse_chain(*, db_path: str | Path, run_id: int) -> list[dict[str, Any]]:
    """Return inverse payloads for this run in reverse chronological order."""
    _ensure_schema(db_path)
    with _connect(db_path) as connection:
        rows = connection.execute(
            "SELECT inverse_json, tool FROM actions WHERE id <= ? ORDER BY id DESC",
            (run_id,),
        ).fetchall()
    return [{"tool": row["tool"], **json.loads(row["inverse_json"])} for row in rows]
