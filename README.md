# twin-agent

[![GitHub](https://img.shields.io/github/license/jp9dotcom/twin-agent)](https://github.com/jp9dotcom/twin-agent)

Twin is a lightweight personal ops agent built around an MCP server for calendar operations. In its current phase, it focuses on safe scheduling workflows: read-only checks, reversible event moves, cancellation previews, and a deterministic risk gate that flags high-impact actions before they run.

## What this project does

Twin provides a small but practical foundation for an agentic calendar assistant:

- Exposes calendar tools via the Model Context Protocol (MCP)
- Uses a SQLite-backed fake calendar backend for local development and testing
- Classifies tool risk using a YAML policy map
- Supports dry-run validation before mutating state
- Tracks action metadata for inverse operations and idempotency safety

## Current scope

This is Phase 1 of the project, and the implementation is intentionally focused on a single domain: calendar management.

Available tools:

- `list_events(start, end)`
- `get_event(event_id)`
- `move_event(event_id, new_start, new_end, dry_run=True)`
- `cancel_event(event_id, dry_run=True)`

The server is built in `twin/servers/calendar_server.py` and runs over stdio, which is the default MCP transport for local tool integrations.

## Architecture

```text
twin-agent/
├── twin/
│   ├── backends/
│   │   ├── base.py        # Calendar backend contract and event model
│   │   └── fake.py        # SQLite implementation used for local/dev work
│   ├── policy/
│   │   ├── gate.py        # Risk classification logic
│   │   └── risk_map.yaml  # Deterministic risk rules for tool actions
│   ├── servers/
│   │   └── calendar_server.py
│   ├── store/
│   │   └── actions.py     # Action journaling and inverse metadata
│   └── __init__.py
├── tests/
│   ├── test_actions_store.py
│   ├── test_calendar_tools.py
│   ├── test_fake_backend.py
│   └── test_gate.py
├── pyproject.toml
├── README.md
└── ...
```

## Risk model

Tool risk is classified through the policy map in `twin/policy/risk_map.yaml`.

The policy currently uses a simple ladder:

- `read` for reads
- `reversible` for safe modifications
- `irreversible-equivalent` for high-impact changes

For example, moving or canceling events with many attendees escalates to a higher-risk decision and triggers `needs_approval`.

## Quick start

### 1. Install dependencies

Using `uv` (recommended):

```bash
uv sync
```

Or with a standard Python environment:

```bash
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> This project is configured for modern Python 3.11+ and uses `uv` conventions in the existing scripts and tests.

### 2. Run the MCP server

```bash
uv run python -m twin.servers.calendar_server
```

The default backend is the fake in-memory/SQLite calendar implementation:

```bash
export TWIN_CALENDAR_BACKEND=fake
```

The project currently supports:

- `fake` — working in Phase 1
- `google` — placeholder, not implemented yet

### 3. Run the test suite

```bash
uv run pytest
```

## Tool behavior

### `list_events`

Lists events whose ranges overlap a requested time window.

Request shape:

```json
{
  "start": "2026-10-27T00:00:00+05:30",
  "end": "2026-10-27T23:59:00+05:30"
}
```

Response:

```json
{
  "events": [
    {
      "id": "evt-1",
      "title": "Team sync",
      "start": "2026-10-26T09:00:00+05:30",
      "end": "2026-10-26T10:00:00+05:30",
      "attendees": ["aisha@example.com", "ben@example.com"],
      "description": "Weekly team coordination meeting.",
      "organizer": "aisha@example.com"
    }
  ],
  "count": 1
}
```

### `get_event`

Fetch a single event by ID.

```json
{
  "event": {
    "id": "evt-1",
    "title": "Team sync",
    "start": "2026-10-26T09:00:00+05:30",
    "end": "2026-10-26T10:00:00+05:30",
    "attendees": ["aisha@example.com"],
    "description": "Weekly team coordination meeting.",
    "organizer": "aisha@example.com"
  }
}
```

### `move_event`

Moves an event to a new time range and returns structured metadata.

Example call:

```json
{
  "event_id": "evt-1",
  "new_start": "2026-10-27T09:00:00+05:30",
  "new_end": "2026-10-27T10:00:00+05:30",
  "dry_run": true
}
```

Example response:

```json
{
  "would_do": "Move 'Team sync' from 2026-10-26T09:00:00+05:30 to ...",
  "affected_attendees": ["aisha@example.com", "ben@example.com"],
  "inverse": {
    "tool": "move_event",
    "args": {
      "event_id": "evt-1",
      "new_start": "2026-10-26T09:00:00+05:30",
      "new_end": "2026-10-26T10:00:00+05:30"
    }
  },
  "risk": "irreversible-equivalent",
  "needs_approval": true,
  "reasons": ["Moving an event with many attendees requires approval."]
}
```

When `dry_run` is `false`, the event is actually moved and the result includes the applied state.

### `cancel_event`

Cancels an event without deleting the event history in the logs until the action is applied.

Example:

```json
{
  "event_id": "evt-1",
  "dry_run": true
}
```

The server returns the planned cancellation and risk metadata; when applied, it includes `applied: true`.

## Data and safety notes

Twin is designed around safe automated operations rather than unrestricted mutation:

- mutating tools default to `dry_run=True`
- event-level conflicts are checked before writes
- risk decisions are deterministic and inspectable
- action logging is kept separate from the calendar backend
- inverse payloads support undo-style workflows

## Current limitations

This repository is intentionally narrow in scope:

- only the fake calendar backend is implemented
- no real Google Calendar integration yet
- no full agent orchestration layer beyond the MCP server
- policy is YAML-driven and intentionally deterministic rather than ML-based

## Development notes

The package is set up as a minimal Python project with a standard layout:

```bash
uv run pytest
uv run ruff check .
```

The test suite verifies:

- dry-run behavior
- invalid input handling
- event movement and cancellation semantics
- inverse operation restoration
- risk escalation decisions
- idempotent action storage

## License

This project is currently a prototype / personal utility repository and does not yet specify a formal license.
