"""The single emitter of the oversight, agents, QMS and incident summaries.

`check` calls `with_summaries` right before signing, so the signature covers the
summaries and `push` forwards them unchanged. Metadata only (E-5): counts, enums,
`YYYY-MM-DD` days and log heads. Never a name, description, note, rationale, tool
or agent id. No clock (E-14): every date comes from a log entry or the register.

Each builder returns `(model | None, anchors)`; `anchors` are `sha256:`-prefixed
log heads destined for `evidence_hashes`. A source that cannot be read becomes a
warning and an omitted sub-object, never a failed `check`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from opencomplai_core.agent_inventory import AgentInventory
from opencomplai_core.agent_log_verify import verify_agent_log
from opencomplai_core.agent_sources import cross_check, detected
from opencomplai_core.gap_probes import INCIDENT_LOG_PATH, qms_clause_results
from opencomplai_core.incident import PartyKind, load_register, parse_ts
from opencomplai_core.models import ScanStatusArtifact, SystemManifest
from opencomplai_core.signed_log import SignedLog, verify_log
from opencomplai_core.signing import SigningDomain
from opencomplai_core.summaries import (
    AgentsSummary,
    ArtifactSummaries,
    IncidentItem,
    IncidentsSummary,
    OversightSummary,
    QmsClauses,
    QmsSummary,
)

from opencomplai_cli.commands.oversight_log import log_path

_MAX_ITEMS = 50
_PREFIX = "sha256:"
_DEFAULT_AGENT_LOG = "agent-log.jsonl"  # the Art. 12 probe's SDK default name
_DEFAULT_REGISTER = "incident-register.json"
_PARTY_ORDER = (
    PartyKind.authority,
    PartyKind.deployer,
    PartyKind.importer,
    PartyKind.distributor,
)


def _day(ts: str) -> str:
    return parse_ts(ts).date().isoformat()


def _leaf(head: str) -> str:
    return head.removeprefix(_PREFIX)


def build_oversight(
    log_path: Path, system_id: str
) -> tuple[OversightSummary | None, list[str]]:
    """Counts for one system; the head is the whole log's.

    `chain_valid` is chain integrity only (no public key is passed), NOT a
    signature check: `opencomplai verify --kind oversight-log` does that.
    """
    if not log_path.is_file():
        return None, []
    payloads = []
    last_ts = None
    for e in SignedLog(log_path, SigningDomain.OVERSIGHT_LOG).entries():
        p = e.get("payload") if isinstance(e, dict) else None
        if isinstance(p, dict) and p.get("system_id") == system_id:
            payloads.append(p)
            try:
                last_ts = _day(e["ts"])
            except (KeyError, ValueError):
                pass
    if not payloads:
        return None, []
    v = verify_log(log_path, SigningDomain.OVERSIGHT_LOG)
    head = v.head if v.count else None
    summary = OversightSummary(
        entries=len(payloads),
        approvals=sum(p.get("event") == "approval_minted" for p in payloads),
        resumes=sum(p.get("event") == "resume_granted" for p in payloads),
        roles=len({p["role"] for p in payloads if p.get("role")}),
        last_event_on=last_ts,
        chain_valid=v.ok,
        log_head_sha256=_leaf(head) if head else None,
    )
    return summary, [head] if head else []


def build_agents(
    manifest: SystemManifest, agent_log: Path | None, scan_report: Any
) -> tuple[AgentsSummary | None, list[str]]:
    """None without a declared inventory: the required counts would be invented."""
    inventory: AgentInventory | None = manifest.agent_inventory
    if inventory is None:
        return None, []
    fields: dict[str, Any] = {
        "agents": len(inventory.agents),
        "with_mandate": sum(a.mandate is not None for a in inventory.agents),
        "with_guardrails": sum(bool(a.guardrails) for a in inventory.agents),
    }
    if scan_report is not None:
        fields["undeclared"] = len(
            cross_check(inventory, detected(scan_report)).undeclared
        )
    anchors: list[str] = []
    if agent_log is not None and agent_log.is_file():
        report = verify_agent_log(agent_log, inventory=inventory)
        fields["log_entries"] = report.chain.count
        fields["chain_valid"] = report.chain.ok
        if report.mandate_checked:
            fields["out_of_mandate"] = len(report.out_of_mandate)
        if report.chain.count:
            fields["log_head_sha256"] = _leaf(report.chain.head)
            anchors.append(report.chain.head)
    return AgentsSummary(**fields), anchors


def build_qms(repo_root: Path, manifest: SystemManifest) -> QmsSummary | None:
    """None (absent) when every clause is missing and no organisation size is declared."""
    results = qms_clause_results(repo_root)
    size = manifest.organisation_size
    if size is None and all(r.label == "Missing" for r in results):
        return None
    clauses = {r.letter: r.label.lower() for r in results}
    return QmsSummary(clauses=QmsClauses(**clauses), size_tier=size)


def build_incidents(
    register_path: Path, system_id: str, *, log_path: Path | None = None
) -> tuple[IncidentsSummary | None, list[str]]:
    """Reads class, dates and party kinds only; never description, note, party or ref."""
    records = [
        r for r in load_register(register_path).incidents if r.system_id == system_id
    ]
    if not records:
        return None, []
    items = []
    for r in sorted(records, key=lambda r: (r.declared_at, r.id), reverse=True)[
        :_MAX_ITEMS
    ]:
        authority = [
            n.sent_at for n in r.notifications if n.kind == PartyKind.authority
        ]
        kinds = {n.kind for n in r.notifications}
        items.append(
            IncidentItem(
                incident_id=r.id,
                incident_class=r.incident_class.value,
                status="closed" if r.closed_at else "open",
                declared_on=_day(r.declared_at),
                aware_on=_day(r.aware_at),
                reported_on=_day(min(authority, key=parse_ts)) if authority else None,
                closed_on=_day(r.closed_at) if r.closed_at else None,
                party_types=[k.value for k in _PARTY_ORDER if k in kinds],
            )
        )
    closed = sum(bool(r.closed_at) for r in records)
    summary = IncidentsSummary(open=len(records) - closed, closed=closed, items=items)
    log = log_path or register_path.parent / INCIDENT_LOG_PATH
    if not log.is_file():
        return summary, []
    v = verify_log(log, SigningDomain.INCIDENT_LOG)
    return summary, [v.head] if v.count else []


def with_summaries(
    artifact: ScanStatusArtifact,
    *,
    manifest: SystemManifest,
    repo_root: Path,
    scan_report: Any,
    oversight_log: Path | None,
    agent_log: Path | None,
    incident_register: Path | None,
    warn: Callable[[str], None],
) -> ScanStatusArtifact:
    """Add the four summaries, keeping `packs`; the same object when none applies.

    `warn` gets fixed text only (source name and exception class), never exception
    text, which could echo log content.
    """
    sid = manifest.system_id
    oversight_log = oversight_log or log_path()
    agent_log = agent_log or Path(_DEFAULT_AGENT_LOG)
    incident_register = incident_register or Path(_DEFAULT_REGISTER)
    found: dict[str, Any] = {}
    anchors: list[str] = []
    sources = {
        "oversight": lambda: build_oversight(oversight_log, sid),
        "agents": lambda: build_agents(manifest, agent_log, scan_report),
        "qms": lambda: (build_qms(repo_root, manifest), []),
        "incidents": lambda: build_incidents(incident_register, sid),
    }
    for name, build in sources.items():
        try:
            model, heads = build()
        except (OSError, ValueError, TypeError, KeyError) as exc:
            warn(f"{name} summary omitted ({type(exc).__name__})")
            continue
        if model is not None:
            found[name] = model
            anchors += heads
    if not found:
        return artifact
    summaries = (artifact.summaries or ArtifactSummaries()).model_copy(update=found)
    merged = list(dict.fromkeys([*artifact.evidence_hashes, *anchors]))
    return artifact.model_copy(
        update={"summaries": summaries, "evidence_hashes": merged}
    )
