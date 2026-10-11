"""
Persistence for the HITL deployment state machine (HALT-WIRE).

`state_machine.transition()` computes the *rule* for a state change — it is
pure and takes no dependency on storage. This module is the one place that
reads/writes the *fact* of a system's current state to disk: a single JSON
file, keyed by `system_id`, so multiple systems tracked by the same
Opencomplai install stay independently halted/running.

No service dependency today — the CLI (`opencomplai check` / `approve` /
`resume` / `docs generate`) is the only caller (E-12), so callers choose
where the file lives (the CLI passes its own config directory, overridable
via `OPENCOMPLAI_STATE_DIR` for tests/CI).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from opencomplai_core.models import SystemState

_STATE_FILE_NAME = "system-state.json"


def _state_file(state_dir: Path) -> Path:
    return state_dir / _STATE_FILE_NAME


def _read_all(state_dir: Path) -> dict:
    path = _state_file(state_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # A corrupt or unreadable state file must not crash every subsequent
        # check/docs-generate call — treat it as "no record", the same as a
        # fresh install. The next save_state() call rewrites it cleanly.
        return {}


def load_state(state_dir: Path, system_id: str) -> SystemState:
    """Return the persisted state for `system_id`.

    Defaults to RUNNING when no record exists — a system this store has
    never seen halted is, by definition, running.
    """
    record = _read_all(state_dir).get(system_id)
    if record is None:
        return SystemState.RUNNING
    return SystemState(record["state"])


def save_state(
    state_dir: Path,
    system_id: str,
    state: SystemState,
    *,
    reason: str,
    commit_ref: str,
) -> None:
    """Persist `state` for `system_id`, overwriting any prior record for
    that system only — other systems' records are left untouched."""
    state_dir.mkdir(parents=True, exist_ok=True)
    records = _read_all(state_dir)
    records[system_id] = {
        "state": state.value,
        "changed_at": datetime.now(UTC).isoformat(),
        "reason": reason,
        "commit_ref": commit_ref,
    }
    _state_file(state_dir).write_text(
        json.dumps(records, indent=2, sort_keys=True), encoding="utf-8"
    )


def state_record(state_dir: Path, system_id: str) -> dict | None:
    """Return the full persisted record for `system_id` (state, changed_at,
    reason, commit_ref), or None if this system has never been recorded."""
    return _read_all(state_dir).get(system_id)
