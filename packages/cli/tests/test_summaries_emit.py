"""SU-139: the four metadata-only summaries `check` emits, built from local evidence."""

from __future__ import annotations

import json
from pathlib import Path

import opencomplai_cli.summaries_emit as emit
from opencomplai_core import incident
from opencomplai_core.gap_probes import INCIDENT_LOG_PATH
from opencomplai_core.models import (
    CorroborationReport,
    ScanResult,
    ScanStatusArtifact,
    SystemManifest,
)
from opencomplai_core.signed_log import SignedLog
from opencomplai_core.signing import SigningDomain
from opencomplai_core.summaries import ArtifactSummaries, OversightSummary

SYS = "sys-1"
SENTINEL = "SENTINEL-free-text-91c2"
TS = "2026-03-01T10:00:00+00:00"

_FILLED = (
    "This procedure documents regulatory compliance, design control, quality "
    "assurance, testing validation, technical specifications and standards, "
    "data governance, risk management and accountability for the system.\n"
)


def _agent(agent_id="a1", *, mandate=True, guardrail=True, tools=("search",)) -> dict:
    return {
        "id": agent_id,
        "name": f"{SENTINEL}-name",
        "tools": [{"name": t, "kind": "function"} for t in tools],
        "mandate": {"permitted_actions": ["search"]} if mandate else None,
        "guardrails": [{"kind": "filter"}] if guardrail else [],
    }


def _manifest(agents: list[dict] | None = None, **extra) -> SystemManifest:
    if agents is not None:
        extra["agent_inventory"] = {"agents": agents}
    return SystemManifest(
        system_id=SYS,
        intended_purpose="customer support chatbot",
        compliance_target="EU_AI_ACT",
        high_risk_presumption=False,
        commit_ref="HEAD",
        **extra,
    )


def _artifact(**kw) -> ScanStatusArtifact:
    return ScanStatusArtifact(
        install_id="i",
        system_id=SYS,
        commit_ref="c",
        result=ScanResult.PASS,
        rationale_hash="sha256:a",
        duration_ms=1,
        **kw,
    )


def _oversight_log(path: Path, entries: list[tuple[str, dict]]) -> Path:
    log = SignedLog(path, SigningDomain.OVERSIGHT_LOG)
    for ts, payload in entries:
        log.append(payload, ts=ts)
    return path


def _entry(event="approval_minted", system_id=SYS, role="Officer") -> dict:
    return {"event": event, "system_id": system_id, "role": role}


def _agent_log(path: Path, tools: list[str], agent_id="a1") -> Path:
    log = SignedLog(path, SigningDomain.AGENT_LOG)
    for tool in tools:
        log.append(
            {
                "agent_id": agent_id,
                "tool": tool,
                "intent": SENTINEL,
                "outside_mandate": False,
            },
            ts=TS,
        )
    return path


def _run(artifact=None, *, manifest=None, repo=None, tmp_path: Path, **kw):
    warnings: list[str] = []
    args = {
        "manifest": manifest or _manifest(),
        "repo_root": repo if repo is not None else tmp_path / "repo",
        "scan_report": None,
        "oversight_log": tmp_path / "none-oversight.json",
        "agent_log": tmp_path / "none-agent.jsonl",
        "incident_register": tmp_path / "none-register.json",
        "warn": warnings.append,
    } | kw
    out = emit.with_summaries(artifact or _artifact(), **args)
    return out, warnings


def _register(path: Path, system_id=SYS, n=1) -> incident.IncidentRegister:
    reg = incident.IncidentRegister()
    for i in range(n):
        incident.declare(
            reg,
            system_id=system_id,
            declared_at=f"2026-04-{i % 28 + 1:02d}T08:00:00Z",
            aware_at=f"2026-04-{i % 28 + 1:02d}T07:00:00Z",
            description=f"{SENTINEL} description",
        )
    incident.save_register(path, reg)
    return reg


# --- oversight ---------------------------------------------------------------


def test_oversight_counts_roles_and_last_event_day(tmp_path):
    path = _oversight_log(
        tmp_path / "o.json",
        [
            ("2026-03-01T10:00:00+00:00", _entry(role="Officer")),
            ("2026-03-02T10:00:00+00:00", _entry("resume_granted", role="Lead")),
            ("2026-03-05T23:30:00+00:00", _entry(role="Officer")),
            ("not a time", _entry(role=None)),
        ],
    )
    s, anchors = emit.build_oversight(path, SYS)
    assert (s.entries, s.approvals, s.resumes, s.roles) == (4, 3, 1, 2)
    assert s.last_event_on == "2026-03-05"
    assert s.chain_valid is True
    assert anchors == ["sha256:" + s.log_head_sha256]


def test_oversight_filters_by_system_id(tmp_path):
    path = _oversight_log(
        tmp_path / "o.json",
        [(TS, _entry()), (TS, _entry(system_id="other"))],
    )
    s, _ = emit.build_oversight(path, SYS)
    assert s.entries == 1
    assert emit.build_oversight(path, "nobody") == (None, [])
    # the head is the whole log's, whichever system asked
    assert s.log_head_sha256 == SignedLog(path, SigningDomain.OVERSIGHT_LOG).head()[7:]


def test_oversight_missing_log_is_none(tmp_path):
    assert emit.build_oversight(tmp_path / "missing.json", SYS) == (None, [])


def test_oversight_tampered_chain_reports_chain_valid_false(tmp_path):
    path = _oversight_log(tmp_path / "o.json", [(TS, _entry()), (TS, _entry())])
    lines = [json.loads(x) for x in path.read_text("utf-8").splitlines()]
    lines[1]["payload"]["role"] = "Intruder"
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
    s, _ = emit.build_oversight(path, SYS)
    assert s.chain_valid is False


# --- agents ------------------------------------------------------------------


def test_agents_counts_mandates_guardrails(tmp_path):
    m = _manifest([_agent("a1"), _agent("a2", mandate=False, guardrail=False)])
    s, anchors = emit.build_agents(m, None, None)
    assert (s.agents, s.with_mandate, s.with_guardrails) == (2, 1, 1)
    assert (s.undeclared, s.log_entries, s.out_of_mandate) == (None, None, None)
    assert (s.chain_valid, s.log_head_sha256, anchors) == (None, None, [])


def test_agents_undeclared_only_with_scan_report(tmp_path):
    report = CorroborationReport.model_validate(_scan_json())
    m = _manifest([_agent()])
    assert emit.build_agents(m, None, None)[0].undeclared is None
    assert emit.build_agents(m, None, report)[0].undeclared == 1


def _scan_json() -> dict:
    ev = {
        "evidence_id": "ev0",
        "evidence_kind": "import",
        "category": "mcp_server",
        "token_hash": "h",
        "token_label": "mcp",
        "locations": ["src/a.py:1"],
        "scope": "prod",
        "reachability": "reachable_entrypoint",
        "detector_id": "d",
        "detector_version": "1",
        "redaction_level": "none",
        "rationale_code": "r",
        "confidence": 0.9,
    }
    finding = {
        "finding_id": "f0",
        "signal_category": "mcp_server",
        "evidence_ids": ["ev0"],
        "locations": ["src/a.py:1"],
        "mapped_taxonomy": [],
        "strength": 1.0,
        "scope": "prod",
        "reachability": "reachable_entrypoint",
        "confidence_rationale": [],
        "reviewer_prompt": "",
    }
    return {
        "scan_id": "s",
        "system_id": SYS,
        "commit_ref": "HEAD",
        "scanner_version": "0",
        "input_digest": "sha256:a",
        "config_hash": "sha256:b",
        "detector_versions": {},
        "declared_purpose": "x",
        "declared_categories": [],
        "evidence": [ev],
        "findings": [finding],
        "detected_categories": [],
        "discrepancies": [],
        "score_breakdown": {},
        "severity": "none",
        "feature_summary": {},
        "cache_summary": {},
        "skipped_paths": [],
        "limits_hit": [],
        "warnings": [],
        "detector_errors": [],
        "baseline_ref": None,
        "generated_at": "2026-03-01T00:00:00Z",
        "report_hash": "sha256:c",
    }


def test_agents_log_adds_chain_and_out_of_mandate(tmp_path):
    log = _agent_log(tmp_path / "a.jsonl", ["search", "search", "delete"])
    s, anchors = emit.build_agents(_manifest([_agent()]), log, None)
    assert (s.log_entries, s.chain_valid, s.out_of_mandate) == (3, True, 1)
    assert anchors == ["sha256:" + s.log_head_sha256]


def test_agents_without_inventory_is_none_even_with_log(tmp_path):
    log = _agent_log(tmp_path / "a.jsonl", ["search"])
    assert emit.build_agents(_manifest(), log, None) == (None, [])


# --- qms ---------------------------------------------------------------------


def test_qms_maps_labels_to_clause_enum(tmp_path):
    (tmp_path / "REGULATORY_COMPLIANCE_STRATEGY.md").write_text(_FILLED, "utf-8")
    (tmp_path / "RISK_MANAGEMENT_SYSTEM.md").write_text("_fill in_\n", "utf-8")
    s = emit.build_qms(tmp_path, _manifest())
    c = s.clauses
    assert (c.a, c.g, c.b, c.m) == ("present", "unfilled", "missing", "missing")
    assert s.size_tier is None


def test_qms_all_missing_without_size_is_none(tmp_path):
    assert emit.build_qms(tmp_path, _manifest()) is None


def test_qms_all_missing_with_size_is_emitted(tmp_path):
    s = emit.build_qms(tmp_path, _manifest(organisation_size="small"))
    assert s.size_tier == "small"
    assert set(s.clauses.model_dump().values()) == {"missing"}


def test_qms_undeclared_size_is_none_never_unknown(tmp_path):
    (tmp_path / "DESIGN_CONTROL.md").write_text(_FILLED, "utf-8")
    s = emit.build_qms(tmp_path, _manifest())
    assert s.size_tier is None
    assert "unknown" not in s.model_dump_json()


# --- incidents ---------------------------------------------------------------


def test_incidents_newest_first_capped_at_50_counts_all(tmp_path):
    path = tmp_path / "r.json"
    reg = _register(path, n=55)
    incident.close(reg, "INC-0001", "2026-05-01T00:00:00Z", "done")
    incident.save_register(path, reg)
    s, _ = emit.build_incidents(path, SYS)
    assert (s.open, s.closed, len(s.items)) == (54, 1, 50)
    days = [(i.declared_on, i.incident_id) for i in s.items]
    assert days == sorted(days, reverse=True)
    assert s.items[-1].declared_on >= "2026-04-01"


def test_incidents_party_types_and_reported_on_from_authority_notifications(tmp_path):
    path = tmp_path / "r.json"
    reg = _register(path)
    for party, kind, sent in (
        ("Dist Co", "distributor", "2026-04-02T00:00:00Z"),
        ("Late Authority", "authority", "2026-04-09T00:00:00Z"),
        ("Early Authority", "authority", "2026-04-03T00:00:00Z"),
        ("Deployer Co", "deployer", "2026-04-04T00:00:00Z"),
    ):
        incident.add_notification(
            reg, "INC-0001", incident.Notification(party=party, kind=kind, sent_at=sent)
        )
    incident.save_register(path, reg)
    (item,) = emit.build_incidents(path, SYS)[0].items
    assert item.reported_on == "2026-04-03"
    assert item.party_types == ["authority", "deployer", "distributor"]
    assert (item.status, item.closed_on) == ("open", None)
    assert (item.declared_on, item.aware_on) == ("2026-04-01", "2026-04-01")


def test_incidents_other_system_ignored(tmp_path):
    path = tmp_path / "r.json"
    _register(path, system_id="other")
    assert emit.build_incidents(path, SYS) == (None, [])
    assert emit.build_incidents(tmp_path / "missing.json", SYS) == (None, [])


def test_incident_free_text_never_in_model_dump(tmp_path):
    path = tmp_path / "r.json"
    reg = _register(path)
    incident.add_notification(
        reg,
        "INC-0001",
        incident.Notification(
            party=SENTINEL,
            kind="authority",
            sent_at="2026-04-02T00:00:00Z",
            ref=SENTINEL,
        ),
    )
    incident.close(reg, "INC-0001", "2026-04-05T00:00:00Z", SENTINEL)
    incident.save_register(path, reg)
    s, _ = emit.build_incidents(path, SYS)
    assert SENTINEL not in s.model_dump_json()
    assert (s.items[0].status, s.items[0].closed_on) == ("closed", "2026-04-05")


def test_incident_log_head_is_anchor_only(tmp_path):
    path = tmp_path / "r.json"
    _register(path)
    log = SignedLog(tmp_path / INCIDENT_LOG_PATH, SigningDomain.INCIDENT_LOG)
    log.append({"incident_id": "INC-0001"}, ts=TS)
    s, anchors = emit.build_incidents(path, SYS)
    assert anchors == [log.head()]
    assert "sha256" not in s.model_dump_json()


# --- with_summaries ----------------------------------------------------------


def test_corrupt_register_warns_and_omits(tmp_path):
    reg = tmp_path / "r.json"
    reg.write_text("{ not json", encoding="utf-8")
    artifact = _artifact()
    out, warnings = _run(artifact, tmp_path=tmp_path, incident_register=reg)
    assert out is artifact
    assert warnings == ["incidents summary omitted (ValueError)"]

    log = tmp_path / "o.json"
    log.write_text(f"{SENTINEL} garbage\n", encoding="utf-8")
    out, warnings = _run(artifact, tmp_path=tmp_path, oversight_log=log)
    assert out is artifact
    assert len(warnings) == 1
    assert SENTINEL not in warnings[0]


def test_with_summaries_no_sources_returns_same_object(tmp_path):
    artifact = _artifact()
    out, warnings = _run(artifact, tmp_path=tmp_path)
    assert out is artifact
    assert warnings == []


def test_with_summaries_preserves_packs(tmp_path):
    from opencomplai_core.summaries import PacksSummary

    artifact = _artifact(summaries=ArtifactSummaries(packs=PacksSummary(issued=3)))
    log = _oversight_log(tmp_path / "o.json", [(TS, _entry())])
    out, _ = _run(artifact, tmp_path=tmp_path, oversight_log=log)
    assert out.summaries.packs.issued == 3
    assert isinstance(out.summaries.oversight, OversightSummary)
    assert artifact.summaries.oversight is None  # input not mutated


def test_heads_in_evidence_hashes_and_typed_leaf(tmp_path):
    o_log = _oversight_log(tmp_path / "o.json", [(TS, _entry())])
    a_log = _agent_log(tmp_path / "a.jsonl", ["search"])
    reg = tmp_path / "r.json"
    _register(reg)
    i_log = SignedLog(tmp_path / INCIDENT_LOG_PATH, SigningDomain.INCIDENT_LOG)
    i_log.append({"incident_id": "INC-0001"}, ts=TS)
    kw = {
        "manifest": _manifest([_agent()]),
        "oversight_log": o_log,
        "agent_log": a_log,
        "incident_register": reg,
    }
    out, _ = _run(_artifact(evidence_hashes=["sha256:pre"]), tmp_path=tmp_path, **kw)
    heads = [
        SignedLog(o_log, SigningDomain.OVERSIGHT_LOG).head(),
        SignedLog(a_log, SigningDomain.AGENT_LOG).head(),
        i_log.head(),
    ]
    assert out.evidence_hashes == ["sha256:pre", *heads]
    assert out.summaries.oversight.log_head_sha256 == heads[0][7:]
    assert out.summaries.agents.log_head_sha256 == heads[1][7:]
    assert not hasattr(out.summaries.incidents, "log_head_sha256")
    again, _ = _run(out, tmp_path=tmp_path, **kw)
    assert again.evidence_hashes == out.evidence_hashes


def test_module_never_reads_the_clock():
    src = Path(emit.__file__).read_text(encoding="utf-8")
    for needle in ("datetime.now", "time.time", "date.today", "utcnow"):
        assert needle not in src


def test_module_does_not_import_main():
    src = Path(emit.__file__).read_text(encoding="utf-8")
    assert "opencomplai_cli.main" not in src
    assert "import main" not in src
