"""
Tamper-evident, optionally signed log of an agent's decisions.

A thin SDK layer over the shared hash-chained ``SignedLog`` in ``opencomplai_core``.
Only metadata is stored: the raw tool input is never written, just its SHA-256.

Honest ceiling: a chain cannot detect removal of the newest entries. Store
``head()`` and ``len()`` elsewhere and pass them to ``verify`` as
``expected_head`` / ``expected_count`` to catch truncation. ``verify`` without a
public key checks chain integrity only, not signatures.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from opencomplai_core.signed_log import LogVerification, SignedLog, verify_log
from opencomplai_core.signing import SigningDomain, canonical_json_bytes, resolve_key

_OUTCOMES = ("success", "failure", "blocked")
_MAX_INTENT = 1000
_FIELDS = {
    "agent_id": str,
    "mandate_ref": (str, type(None)),
    "intent": str,
    "tool": str,
    "input_hash": str,
    "outcome": str,
    "outside_mandate": bool,
}


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class AgentDecisionLog:
    def __init__(
        self,
        path: str | Path,
        *,
        signing_key: Path | bytes | None = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._log = SignedLog(Path(path), SigningDomain.AGENT_LOG)
        self._signing_key = signing_key
        self._clock = clock or _utc_now_iso

    def record(
        self,
        *,
        agent_id: str,
        tool: str,
        intent: str,
        tool_input: object,
        outcome: str,
        mandate_ref: str | None = None,
        outside_mandate: bool = False,
    ) -> dict:
        if not agent_id or not tool or not intent:
            raise ValueError("agent_id, tool and intent must be non-empty")
        if len(intent) > _MAX_INTENT:
            raise ValueError(f"intent must be at most {_MAX_INTENT} characters")
        if outcome not in _OUTCOMES:
            raise ValueError(f"outcome must be one of {', '.join(_OUTCOMES)}")
        if not isinstance(outside_mandate, bool):
            raise ValueError("outside_mandate must be a bool")
        key = self._signing_key
        if isinstance(key, Path):
            key = resolve_key(
                key
            )  # raises SigningKeyError; never a silent unsigned entry
        digest = hashlib.sha256(canonical_json_bytes({"input": tool_input}))
        payload = {
            "agent_id": agent_id,
            "mandate_ref": mandate_ref,
            "intent": intent,
            "tool": tool,
            "input_hash": "sha256:" + digest.hexdigest(),
            "outcome": outcome,
            "outside_mandate": outside_mandate,
        }
        return _flatten(self._log.append(payload, ts=self._clock(), private_pem=key))

    def entries(self) -> list[dict]:
        return [_flatten(e) for e in self._log.entries()]

    def head(self) -> str:
        return self._log.head()

    def __len__(self) -> int:
        return len(self._log)

    def verify(
        self,
        *,
        public_key: Path | bytes | None = None,
        require_signed: bool = False,
        expected_head: str | None = None,
        expected_count: int | None = None,
    ) -> LogVerification:
        if isinstance(public_key, Path):
            public_key = public_key.read_bytes()
        result = verify_log(
            self._log.path,
            SigningDomain.AGENT_LOG,
            public_pem=public_key,
            require_signed=require_signed,
            expected_head=expected_head,
            expected_count=expected_count,
        )
        if not result.ok:
            return result
        for e in self._log.entries():
            p = e["payload"]
            if set(p) != set(_FIELDS) or any(
                type(p[k]) not in (t if isinstance(t, tuple) else (t,))
                for k, t in _FIELDS.items()
            ):
                return dataclasses.replace(
                    result, ok=False, error="schema", bad_seq=e["seq"]
                )
        return result


def _flatten(entry: dict) -> dict:
    out = {"seq": entry["seq"], "ts": entry["ts"], **entry["payload"]}
    out["prev_hash"] = entry["prev_hash"]
    out["hash"] = entry["hash"]
    if entry.get("signature"):
        out["signature"] = entry["signature"]
    return out
