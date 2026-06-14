"""
Bias alert fixture data for demo-credit-scoring-v1 and demo-hr-hiring-v2.

Each alert is a valid payload for POST /v1/bias-alerts on the evidence-vault.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

_NOW = datetime.now(tz=UTC)


def _alert(
    *,
    system_id: str,
    severity: str,
    metric: str,
    threshold: float,
    actual: float,  # kept for documentation; not sent to the vault (unsupported field)
    days_ago: float,
    linked_event_id: str | None = None,
) -> dict:
    return {
        "alert_id": str(uuid.uuid4()),
        "system_id": system_id,
        "severity": severity,
        "metric": metric,
        "threshold": threshold,
        "linked_event_id": linked_event_id or str(uuid.uuid4()),
    }


BIAS_ALERTS: list[dict] = [
    # --- credit scoring: HIGH bias trend, mid-period, then recovers ---
    _alert(
        system_id="demo-credit-scoring-v1",
        severity="HIGH",
        metric="demographic_parity_gap",
        threshold=0.10,
        actual=0.18,
        days_ago=55,
    ),
    _alert(
        system_id="demo-credit-scoring-v1",
        severity="HIGH",
        metric="equalised_odds_gap",
        threshold=0.08,
        actual=0.15,
        days_ago=48,
    ),
    _alert(
        system_id="demo-credit-scoring-v1",
        severity="MEDIUM",
        metric="demographic_parity_gap",
        threshold=0.10,
        actual=0.12,
        days_ago=35,
    ),
    _alert(
        system_id="demo-credit-scoring-v1",
        severity="LOW",
        metric="demographic_parity_gap",
        threshold=0.10,
        actual=0.09,
        days_ago=20,
    ),
    # --- hr hiring: bias alerts before and after HITL halt ---
    _alert(
        system_id="demo-hr-hiring-v2",
        severity="HIGH",
        metric="demographic_parity_gap",
        threshold=0.10,
        actual=0.22,
        days_ago=62,
    ),
    _alert(
        system_id="demo-hr-hiring-v2",
        severity="HIGH",
        metric="equalised_odds_gap",
        threshold=0.08,
        actual=0.19,
        days_ago=58,
    ),
    _alert(
        system_id="demo-hr-hiring-v2",
        severity="MEDIUM",
        metric="demographic_parity_gap",
        threshold=0.10,
        actual=0.11,
        days_ago=20,
    ),
    _alert(
        system_id="demo-hr-hiring-v2",
        severity="LOW",
        metric="equalised_odds_gap",
        threshold=0.08,
        actual=0.06,
        days_ago=8,
    ),
]


def get_bias_alerts_for(system_id: str) -> list[dict]:
    return [a for a in BIAS_ALERTS if a["system_id"] == system_id]
