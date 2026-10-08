"""Read back an agent decision log: chain, signatures and mandate compliance.

``verify_agent_log`` checks the hash chain (and signatures when a public key is
given) with ``signed_log.verify_log`` under ``SigningDomain.AGENT_LOG``, then,
only for an intact chain, recomputes from the declared mandate which actions were
out of mandate. The log's own ``outside_mandate`` flag is never trusted: a true
flag is listed as ``self_reported``, a false flag does not hide a computed
finding.

Design choices, not sourced from any standard (see ``MANDATE_RULES``):

* An action string matches a tool by casefolded equality, either ``<name>`` or
  ``tool:<name>`` (the convention of ``agent_inventory``).
* Mandate expiry is judged against each entry's own ``ts``, never the clock.
  A naive timestamp is read as UTC.
* ``mandate.limits`` and the entry's ``mandate_ref`` are NOT evaluated.

Honest ceiling: a chain cannot show that the newest entries were removed; pass
``expected_head`` / ``expected_count`` from a stored anchor to catch that.

No clock, no network. The only file read is the log, through ``verify_log``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from opencomplai_core.agent_inventory import AgentInventory, AgentSpec
from opencomplai_core.signed_log import LogVerification, SignedLog, verify_log
from opencomplai_core.signing import SigningDomain, canonical_json_bytes


def _rule(note: str) -> dict:
    return {
        "source": "design choice of this epic; no external citation",
        "confidence": "low",
        "needs_founder_review": True,
        "note": note,
    }


MANDATE_RULES: dict[str, dict] = {
    "unknown_agent": _rule("agent_id is not in the declared agent inventory"),
    "tool_not_declared": _rule("tool is not among the agent's declared tools"),
    "prohibited_action": _rule("tool matches mandate.prohibited_actions"),
    "not_permitted": _rule(
        "permitted_actions is non-empty and the tool matches none of it"
    ),
    "mandate_expired": _rule("entry ts is later than mandate.expires_at"),
    "bad_timestamp": _rule("ts or expires_at could not be parsed; never a silent pass"),
    "self_reported": _rule("the log entry itself says outside_mandate is true"),
}


def decision_fields(entry: dict) -> dict:
    """The one place an entry is read: nested ``payload`` when present, else flat."""
    body = entry.get("payload")
    body = body if isinstance(body, dict) else entry
    return {
        "agent_id": body.get("agent_id"),
        "tool": body.get("tool"),
        "outside_mandate": body.get("outside_mandate"),
        "ts": entry.get("ts", body.get("ts")),
        "seq": entry.get("seq"),
        "hash": entry.get("hash"),
    }


@dataclass(frozen=True)
class OutOfMandate:
    seq: int | None
    agent_id: str | None
    tool: str | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class AgentLogReport:
    chain: LogVerification
    mandate_checked: bool
    out_of_mandate: tuple[OutOfMandate, ...]

    @property
    def ok(self) -> bool:
        return self.chain.ok and not self.out_of_mandate


def _matches(action: object, tool: str) -> bool:
    a = str(action).casefold()
    t = tool.casefold()
    return a == t or a == "tool:" + t


def _parse(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _reasons(f: dict, agent: AgentSpec | None) -> list[str]:
    tool = f["tool"] if isinstance(f["tool"], str) else ""
    out: list[str] = []
    if agent is None:
        out.append("unknown_agent")
    else:
        if tool.casefold() not in {t.name.casefold() for t in agent.tools}:
            out.append("tool_not_declared")
        m = agent.mandate
        if m is not None:
            if any(_matches(a, tool) for a in m.prohibited_actions):
                out.append("prohibited_action")
            if m.permitted_actions and not any(
                _matches(a, tool) for a in m.permitted_actions
            ):
                out.append("not_permitted")
            if m.expires_at is not None:
                ts, exp = _parse(f["ts"]), _parse(m.expires_at)
                if ts is None or exp is None:
                    out.append("bad_timestamp")
                elif ts > exp:
                    out.append("mandate_expired")
    if f["outside_mandate"] is True:
        out.append("self_reported")
    return out


def check_mandate(
    entries: list[dict], inventory: AgentInventory | None
) -> list[OutOfMandate]:
    """Entries outside the declared mandate; ``[]`` when there is no inventory."""
    if inventory is None:
        return []
    by_id = {a.id: a for a in inventory.agents}
    found: list[OutOfMandate] = []
    for entry in entries:
        f = decision_fields(entry)
        reasons = _reasons(f, by_id.get(f["agent_id"]))
        if reasons:
            found.append(
                OutOfMandate(f["seq"], f["agent_id"], f["tool"], tuple(reasons))
            )
    return found


def verify_agent_log(
    path: Path,
    *,
    public_pem: bytes | None = None,
    require_signed: bool = False,
    expected_head: str | None = None,
    expected_count: int | None = None,
    inventory: AgentInventory | None = None,
) -> AgentLogReport:
    chain = verify_log(
        path,
        SigningDomain.AGENT_LOG,
        public_pem=public_pem,
        require_signed=require_signed,
        expected_head=expected_head,
        expected_count=expected_count,
    )
    if not chain.ok or inventory is None:
        return AgentLogReport(chain, False, ())
    entries = SignedLog(Path(path), SigningDomain.AGENT_LOG).entries()
    return AgentLogReport(chain, True, tuple(check_mandate(entries, inventory)))


def entry_bytes(entry: dict) -> bytes:
    return canonical_json_bytes(entry)


def entry_content_hash(entry: dict) -> str:
    """Same ``sha256:<hex>`` form the evidence vault CAS returns."""
    return "sha256:" + hashlib.sha256(entry_bytes(entry)).hexdigest()


def vault_event_payload(
    system_id: str, entry: dict, content_hash: str, findings: tuple[str, ...]
) -> dict:
    """Ledger payload for one entry: ids, hashes and reason codes, never free text."""
    f = decision_fields(entry)
    return {
        "system_id": system_id,
        "agent_id": f["agent_id"],
        "seq": f["seq"],
        "entry_hash": f["hash"],
        "content_hash": content_hash,
        "tool": f["tool"],
        "outside_mandate": bool(findings),
        "findings": list(findings),
    }
