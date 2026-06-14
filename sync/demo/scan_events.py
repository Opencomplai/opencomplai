"""
Generates 30 time-stamped scan-status artifact payloads per demo system.

Timestamps run backwards from today with ±6-hour jitter so the timeline
chart looks organic. Each system follows a distinct pass/fail narrative.
"""

from __future__ import annotations

import hashlib
import random
import uuid
from datetime import UTC, datetime, timedelta


def _sha256(data: str) -> str:
    return "sha256:" + hashlib.sha256(data.encode()).hexdigest()


def _jittered_timestamps(n: int = 30, span_days: int = 90) -> list[datetime]:
    """Return n datetimes spread over span_days ending now, with ±6 h jitter."""
    now = datetime.now(tz=UTC)
    step = timedelta(days=span_days) / n
    timestamps = []
    for i in range(n):
        base = now - step * (n - 1 - i)
        jitter = timedelta(hours=random.uniform(-6, 6))
        timestamps.append(base + jitter)
    return sorted(timestamps)


# ---------------------------------------------------------------------------
# Per-system narrative generators
# ---------------------------------------------------------------------------


def _events_credit_scoring(timestamps: list[datetime]) -> list[dict]:
    """PASS majority; 3 CONTROL_FAIL events mid-period then recovers."""
    events = []
    fail_window = set(range(12, 15))  # indices 12-14 → mid-period failures
    for i, ts in enumerate(timestamps):
        if i in fail_window:
            result = "fail"
            failed = ["CTRL-002", "CTRL-005"]
        else:
            result = "pass"
            failed = []
        events.append(
            _build_artifact(
                system_id="demo-credit-scoring-v1",
                ts=ts,
                result=result,
                failed_controls=failed,
                pending=0,
                risk_class="HIGH",
                bundle_checksum=_sha256(f"credit-bundle-{i}"),
                control_pass_rate=0.85 if result == "fail" else 0.97,
            )
        )
    return events


def _events_hr_hiring(timestamps: list[datetime]) -> list[dict]:
    """PASS → 5 VALIDATION_FAIL → HITL halt (no scan) → resume → PASS."""
    events = []
    fail_window = set(range(10, 15))  # indices 10-14 → failure streak
    halt_window = set(range(15, 18))  # indices 15-17 → halted (no new scans)
    seq = 0
    for i, ts in enumerate(timestamps):
        if i in halt_window:
            # During HITL halt the system emits no scan status artifacts —
            # skip these slots so there's a visible gap in the timeline chart.
            continue
        if i in fail_window:
            result = "fail"
            failed = ["CTRL-004"]
            pending = random.randint(3, 8)
        else:
            result = "pass"
            failed = []
            pending = 0
        events.append(
            _build_artifact(
                system_id="demo-hr-hiring-v2",
                ts=ts,
                result=result,
                failed_controls=failed,
                pending=pending,
                risk_class="HIGH",
                bundle_checksum=_sha256(f"hr-bundle-{seq}"),
                control_pass_rate=0.78 if result == "fail" else 0.96,
            )
        )
        seq += 1
    return events


def _events_medical_triage(timestamps: list[datetime]) -> list[dict]:
    """All PASS but policy_bundle_version frozen at v1.0.0."""
    return [
        _build_artifact(
            system_id="demo-medical-triage-v1",
            ts=ts,
            result="pass",
            failed_controls=[],
            pending=0,
            risk_class="HIGH",
            bundle_checksum=_sha256("medical-bundle-frozen"),
            policy_bundle_version="v1.0.0",  # intentionally stale — never bumped
            control_pass_rate=0.99,
        )
        for ts in timestamps
    ]


def _events_customer_chat(timestamps: list[datetime]) -> list[dict]:
    """30x PASS, no failures, low pending_verifications_count."""
    return [
        _build_artifact(
            system_id="demo-customer-chat-v1",
            ts=ts,
            result="pass",
            failed_controls=[],
            pending=random.randint(0, 1),
            risk_class="LIMITED",
            bundle_checksum=_sha256(f"chat-bundle-{i}"),
            control_pass_rate=round(random.uniform(0.96, 1.00), 3),
        )
        for i, ts in enumerate(timestamps)
    ]


def _events_inventory_opt(timestamps: list[datetime]) -> list[dict]:
    """30x PASS with very high control_pass_rate (~0.98)."""
    return [
        _build_artifact(
            system_id="demo-inventory-opt-v1",
            ts=ts,
            result="pass",
            failed_controls=[],
            pending=0,
            risk_class="MINIMAL",
            bundle_checksum=_sha256(f"inventory-bundle-{i}"),
            control_pass_rate=round(random.uniform(0.97, 0.99), 3),
        )
        for i, ts in enumerate(timestamps)
    ]


# ---------------------------------------------------------------------------
# Shared artifact builder
# ---------------------------------------------------------------------------


def _build_artifact(
    *,
    system_id: str,
    ts: datetime,
    result: str,
    failed_controls: list[str],
    pending: int,
    risk_class: str,
    bundle_checksum: str,
    policy_bundle_version: str | None = None,
    control_pass_rate: float = 1.0,
) -> dict:
    commit_ref = "git:" + uuid.uuid4().hex[:12]
    rationale_seed = f"{system_id}-{ts.isoformat()}-{result}"
    return {
        "system_id": system_id,
        "commit_ref": commit_ref,
        "result": result,
        "failed_controls": failed_controls,
        "pending_verifications_count": pending,
        "rationale_hash": _sha256(rationale_seed),
        "bundle_checksum": bundle_checksum,
        "risk_class": risk_class,
        "timestamp": ts.isoformat(),
        # Extra fields consumed by metrics ingest (not sent to status-artifact endpoint)
        "_metrics": {
            "system_id": system_id,
            "pass_count": 1 if result == "pass" else 0,
            "fail_count": 0 if result == "pass" else 1,
            "control_pass_rate": control_pass_rate,
            "control_fail_rate": round(1.0 - control_pass_rate, 3),
            "timestamp": ts.isoformat(),
        },
        "_policy_bundle_version": policy_bundle_version,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_GENERATORS = {
    "demo-credit-scoring-v1": _events_credit_scoring,
    "demo-hr-hiring-v2": _events_hr_hiring,
    "demo-medical-triage-v1": _events_medical_triage,
    "demo-customer-chat-v1": _events_customer_chat,
    "demo-inventory-opt-v1": _events_inventory_opt,
}


def generate_scan_events(system_id: str, seed: int = 42) -> list[dict]:
    """Return the list of scan-status artifact dicts for a given system_id."""
    random.seed(seed)
    timestamps = _jittered_timestamps()
    generator = _GENERATORS[system_id]
    return generator(timestamps)
