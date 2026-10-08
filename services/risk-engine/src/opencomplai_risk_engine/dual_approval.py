"""Pure helpers for completing dual-control HITL overrides (REQ-HITL-001).

No I/O here: main.py owns the vault and ledger calls. State lives in the same
durable key-value store as override idempotency, under two derived keys.
"""

from typing import Literal

from pydantic import BaseModel


class SecondApprovalRequest(BaseModel):
    """Request body for POST /v1/hitl/overrides/{override_id}/second-approval."""

    actor_id: str
    rationale: str
    rationale_hash: str  # the first approval's hash
    decision: Literal["approved", "rejected"] = "approved"


class SecondApprovalError(Exception):
    def __init__(self, status: int, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.error_code = error_code
        self.message = message


def pending_key(override_id: str) -> str:
    return f"dual:{override_id}"


def done_key(override_id: str) -> str:
    return f"dual-done:{override_id}"


def pending_record(
    case_id: str, actor_id: str, decision: str, rationale_hash: str
) -> dict:
    return {
        "case_id": case_id,
        "actor_id": actor_id,
        "decision": decision,
        "rationale_hash": rationale_hash,
    }


def _norm(actor_id: str) -> str:
    return actor_id.strip().casefold()


def check_second_approval(
    pending: dict | None,
    done: dict | None,
    actor_id: str,
    first_rationale_hash: str,
) -> None:
    """Raise SecondApprovalError unless this request may complete the override."""
    if pending is None:
        raise SecondApprovalError(404, "NOT_FOUND", "No pending dual-control override")
    if done is not None:
        raise SecondApprovalError(
            409, "ALREADY_COMPLETED", "Override already completed"
        )
    if _norm(actor_id) == _norm(pending["actor_id"]):
        raise SecondApprovalError(
            403, "POLICY_DENIED", "Second approver must differ from the first"
        )
    if first_rationale_hash != pending["rationale_hash"]:
        raise SecondApprovalError(
            409,
            "RATIONALE_HASH_MISMATCH",
            "rationale_hash does not match the first approval",
        )
