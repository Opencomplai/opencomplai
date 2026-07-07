"""
Egress allowlist enforcement (REQ-ARC-001, PRD §4.2).

Only the fields listed in ALLOWED_FIELDS may appear in outbound metadata
sync payloads. Any other field is forbidden and causes a fail-closed block.

Allowed destinations are configured via the EGRESS_ALLOWLIST environment
variable (newline-separated URL prefixes). An empty allowlist blocks all
outbound requests.
"""

from __future__ import annotations

import hashlib
import json
import os

# PRD §4.2 "Dashboard ingest data classes" — these are the ONLY fields
# permitted in outbound metadata sync payloads.
# ISO 27001 A.8.20 / SOC 2 CC6.6 / NIST PR.DS — only these fields may leave the system boundary.
# Any key not in this set is blocked at the egress layer (fail-closed).
# See docs/deployment/security-hardening.md § Egress Control.
ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "system_id",
        "commit_ref",
        "policy_bundle_version",
        "risk_class",
        "control_pass_rate",
        "control_fail_rate",
        "pending_verifications_count",
        "bundle_checksum",
        "size_bytes",
        "signed_by",
        "timestamp",
        "pass_count",
        "fail_count",
        "trap_frequency",
        "override_rate",
        "eval_set_id",
        "eval_overall_outcome",
        "eval_failed_evaluator_ids",
    }
)


def load_allowed_destinations() -> list[str]:
    """
    Return configured allowlisted destination URL prefixes.

    Reads EGRESS_ALLOWLIST env var (newline-separated). An empty list means
    all outbound destinations are blocked (fail-closed default).
    """
    raw = os.environ.get("EGRESS_ALLOWLIST", "")
    return [d.strip() for d in raw.strip().splitlines() if d.strip()]


def validate_payload(payload: dict) -> tuple[bool, list[str]]:
    """
    Validate that payload contains only ALLOWED_FIELDS.

    Returns:
        (True, [])               — all fields are allowlisted
        (False, [forbidden, …])  — at least one forbidden field present
    """
    forbidden = [k for k in payload if k not in ALLOWED_FIELDS]
    return len(forbidden) == 0, forbidden


def validate_destination(url: str) -> bool:
    """
    Return True if url starts with one of the allowlisted destination prefixes.

    An empty allowlist always returns False (fail-closed).
    """
    allowed = load_allowed_destinations()
    if not allowed:
        return False
    return any(url.startswith(dest) for dest in allowed)


def compute_policy_hash() -> str:
    """
    Return a stable SHA-256 hash of the current allowlist configuration.

    Used as policy_hash in EGRESS_BLOCKED events so auditors can tell
    which policy version was active when the block occurred.
    """
    config = {
        "allowed_fields": sorted(ALLOWED_FIELDS),
        "allowed_destinations": sorted(load_allowed_destinations()),
    }
    return f"sha256:{hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()}"
