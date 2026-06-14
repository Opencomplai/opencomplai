"""
HITL halt/resume ledger event fixtures for demo-hr-hiring-v2.

The seeder appends these directly to the evidence-vault ledger via
POST /v1/evidence/events so that the HITL state machine is visible
in the audit trail even when the gateway-api HITL routes are not called.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

_NOW = datetime.now(tz=UTC)

# HITL halt fired ~65 days ago; resume came ~50 days ago (15-day review window)
_HALT_TS = (_NOW - timedelta(days=65)).isoformat()
_RESUME_TS = (_NOW - timedelta(days=50)).isoformat()

HITL_EVENTS: list[dict] = [
    {
        "event_type": "hitl_halt",
        "payload": {
            "system_id": "demo-hr-hiring-v2",
            "reason": "Disparate-impact threshold exceeded on gender axis (CTRL-004 failed x5).",
            "halted_by": "automated-compliance-gate",
            "timestamp": _HALT_TS,
            "triggered_by_control": "CTRL-004",
        },
        "signer_id": "demo-signing-key",
    },
    {
        "event_type": "hitl_review_started",
        "payload": {
            "system_id": "demo-hr-hiring-v2",
            "reviewer": "compliance-officer@demo-tenant.internal",
            "timestamp": _HALT_TS,
            "notes": "Initiating bias remediation sprint; model retrain scheduled.",
        },
        "signer_id": "demo-signing-key",
    },
    {
        "event_type": "hitl_resume",
        "payload": {
            "system_id": "demo-hr-hiring-v2",
            "reason": "Retrained model passed fairness re-validation at reduced threshold.",
            "resumed_by": "compliance-officer@demo-tenant.internal",
            "timestamp": _RESUME_TS,
            "remediation_commit": "git:" + uuid.uuid4().hex[:12],
        },
        "signer_id": "demo-signing-key",
    },
]

# Classification event — logged when the system is first risk-classified
RISK_CLASSIFICATION_EVENTS: dict[str, dict] = {
    system_id: {
        "event_type": "risk_classification",
        "payload": {
            "system_id": system_id,
            "risk_class": risk_class,
            "annex_iii_category": annex_cat,
            "classified_by": "demo-seeder",
            "timestamp": (_NOW - timedelta(days=91)).isoformat(),
        },
        "signer_id": "demo-signing-key",
    }
    for system_id, risk_class, annex_cat in [
        ("demo-credit-scoring-v1", "HIGH", "Art. 6 + Annex III §5b"),
        ("demo-hr-hiring-v2", "HIGH", "Annex III §4a"),
        ("demo-medical-triage-v1", "HIGH", "Annex III §1a"),
        ("demo-customer-chat-v1", "LIMITED", "Art. 50 transparency"),
        ("demo-inventory-opt-v1", "MINIMAL", "Not listed (MINIMAL)"),
    ]
}
