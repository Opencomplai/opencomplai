"""SU-139: `check` emits the four summaries before signing; they survive push.

Fixture repo: an oversight log in the state dir, a manifest with an agent
inventory and organisation size, an agent log, QMS clause files and an
incident register, with sentinel free text in every field that must not leave.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from opencomplai_cli import main
from opencomplai_cli.main import app
from opencomplai_cli.publish import envelope_signature, prepare_scan_status_artifact
from opencomplai_core import incident
from opencomplai_core.deployer_pack import build_pack
from opencomplai_core.models import ScanStatusArtifact, SystemManifest
from opencomplai_core.signed_log import SignedLog
from opencomplai_core.signing import SigningDomain, generate_keypair, verify_artifact
from opencomplai_core.summaries import ArtifactSummaries
from pydantic import ValidationError
from typer.testing import CliRunner

runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA = REPO_ROOT / "dashboard-saas" / "schemas" / "first_scan_status.schema.json"
SYS = "sum-sys"
COMMIT = "a" * 40
SENTINELS = (
    "SENTINEL-incident-desc-5e1",
    "SENTINEL-closure-note-5e1",
    "SENTINEL-agent-id-5e1",
    "SENTINEL-tool-name-5e1",
    "SENTINEL-party-5e1",
)
DESC, NOTE, AGENT, TOOL, PARTY = SENTINELS
TS = "2026-03-01T10:00:00+00:00"
_FILLED = (
    "This procedure documents regulatory compliance, design control, quality "
    "assurance, testing validation, technical specifications and standards, "
    "data governance, risk management, post-market monitoring, incident "
    "reporting, authority communication, record retention, resource planning "
    "and accountability for the system.\n"
)
_CLAUSE_FILES = (
    "REGULATORY_COMPLIANCE_STRATEGY.md",
    "DESIGN_CONTROL.md",
    "QUALITY_MANAGEMENT_PROCEDURES.md",
    "TESTING_VALIDATION.md",
    "TECHNICAL_DOCUMENTATION.md",
    "DATA_GOVERNANCE.md",
    "RISK_MANAGEMENT_SYSTEM.md",
    "POST_MARKET_MONITORING.md",
    "INCIDENT_REPORTING.md",
    "TRANSPARENCY.md",
    "RECORD_KEEPING.md",
    "RESOURCE_MANAGEMENT.md",
)


def _setup(tmp_path: Path, monkeypatch, *, agents: bool = True) -> Path:
    """Chdir to tmp_path, fresh keypair, manifest; returns the public key."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    monkeypatch.delenv("OPENCOMPLAI_VAULT_URL", raising=False)
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setattr(main, "_SIGNING_KEY", key_dir / "signing.key")
    extra = {}
    if agents:
        extra = {
            "organisation_size": "small",
            "agent_inventory": {
                "agents": [
                    {
                        "id": AGENT,
                        "name": AGENT,
                        "tools": [{"name": TOOL, "kind": "function"}],
                        "mandate": {"permitted_actions": [TOOL]},
                        "guardrails": [{"kind": "filter"}],
                    }
                ]
            },
        }
    (tmp_path / "system-manifest.json").write_text(
        SystemManifest(
            system_id=SYS,
            intended_purpose="customer support chatbot",
            compliance_target="EU_AI_ACT",
            high_risk_presumption=False,
            commit_ref="HEAD",
            **extra,
        ).model_dump_json(),
        encoding="utf-8",
    )
    return key_dir / "signing.pub"


def _sources(tmp_path: Path) -> None:
    """Oversight log, agent log, QMS clause files (one scaffold), incident register."""
    state = tmp_path / "state"
    oversight = SignedLog(state / "oversight-log.json", SigningDomain.OVERSIGHT_LOG)
    oversight.append(
        {"event": "approval_minted", "system_id": SYS, "role": "Officer"}, ts=TS
    )
    oversight.append(
        {"event": "resume_granted", "system_id": SYS, "role": "Lead"},
        ts="2026-03-02T10:00:00+00:00",
    )
    agent_log = SignedLog(tmp_path / "agent-log.jsonl", SigningDomain.AGENT_LOG)
    for tool in (TOOL, "other-tool"):
        agent_log.append(
            {"agent_id": AGENT, "tool": tool, "intent": DESC, "outside_mandate": False},
            ts=TS,
        )
    repo = tmp_path / "repo"
    repo.mkdir()
    for name in _CLAUSE_FILES:
        (repo / name).write_text(_FILLED, encoding="utf-8")
    (repo / "ACCOUNTABILITY_FRAMEWORK.md").write_text("_fill in_\n", encoding="utf-8")
    reg = incident.IncidentRegister()
    rec = incident.declare(
        reg,
        system_id=SYS,
        declared_at="2026-04-02T08:00:00Z",
        aware_at="2026-04-01T08:00:00Z",
        description=DESC,
        incident_class=incident.IncidentClass.health_harm,
    )
    incident.add_notification(
        reg,
        rec.id,
        incident.Notification(
            party=PARTY, kind="authority", sent_at="2026-04-03T08:00:00Z", ref=PARTY
        ),
    )
    incident.close(reg, rec.id, "2026-04-09T08:00:00Z", NOTE)
    incident.save_register(tmp_path / "incident-register.json", reg)


def _check(tmp_path: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(tmp_path / "system-manifest.json"),
            "--repo-root",
            str(tmp_path / "repo"),
            "--commit-ref",
            COMMIT,
            *extra,
        ],
    )


def _artifact_text(tmp_path: Path) -> str:
    return (tmp_path / "compliance-artifact.json").read_text(encoding="utf-8")


def _signed_run(tmp_path, monkeypatch):
    pub = _setup(tmp_path, monkeypatch)
    _sources(tmp_path)
    result = _check(tmp_path, "--sign")
    assert result.exit_code == 0, result.output
    return pub, _artifact_text(tmp_path)


def test_check_emits_all_four_summaries_valid_against_closed_schema(
    tmp_path, monkeypatch
):
    if not SCHEMA.exists():
        pytest.skip(
            "dashboard-saas/schemas/first_scan_status.schema.json not reachable"
        )
    _, text = _signed_run(tmp_path, monkeypatch)
    s = json.loads(text)["summaries"]
    assert (s["oversight"]["entries"], s["oversight"]["roles"]) == (2, 2)
    assert s["oversight"]["last_event_on"] == "2026-03-02"
    assert (s["agents"]["agents"], s["agents"]["out_of_mandate"]) == (1, 1)
    assert s["qms"]["size_tier"] == "small"
    assert s["qms"]["clauses"]["a"] == "present"
    assert s["qms"]["clauses"]["m"] == "unfilled"
    assert s["incidents"] == {
        "open": 0,
        "closed": 1,
        "items": [
            {
                "incident_id": "INC-0001",
                "incident_class": "health_harm",
                "status": "closed",
                "declared_on": "2026-04-02",
                "aware_on": "2026-04-01",
                "reported_on": "2026-04-03",
                "closed_on": "2026-04-09",
                "party_types": ["authority"],
            }
        ],
    }
    prepared = prepare_scan_status_artifact(
        json.loads(text), commit_env={"GITHUB_SHA": COMMIT}
    )
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = [
        e.message for e in jsonschema.Draft202012Validator(schema).iter_errors(prepared)
    ]
    assert errors == []


def test_signature_covers_summaries_and_survives_prepare(tmp_path, monkeypatch):
    pub, text = _signed_run(tmp_path, monkeypatch)
    original = json.loads(text)
    artifact = ScanStatusArtifact.model_validate_json(text)
    assert artifact.summaries is not None
    assert verify_artifact(artifact, pub) is True
    prepared = prepare_scan_status_artifact(original, commit_env={"GITHUB_SHA": COMMIT})
    assert prepared["summaries"] == original["summaries"]
    assert envelope_signature(original, prepared) == original["signature"] != ""
    # the heads are anchors in evidence_hashes, prefix kept
    heads = {SignedLog(tmp_path / "agent-log.jsonl", SigningDomain.AGENT_LOG).head()}
    assert heads <= set(original["evidence_hashes"])


def test_tampered_summaries_break_signature(tmp_path, monkeypatch):
    pub, text = _signed_run(tmp_path, monkeypatch)
    data = json.loads(text)
    data["summaries"]["oversight"]["entries"] += 1
    tampered = ScanStatusArtifact.model_validate(data)
    assert verify_artifact(tampered, pub) is False


def test_sentinels_never_appear_in_artifact_or_envelope(tmp_path, monkeypatch):
    _, text = _signed_run(tmp_path, monkeypatch)
    envelope = json.dumps(
        prepare_scan_status_artifact(
            json.loads(text), commit_env={"GITHUB_SHA": COMMIT}
        )
    )
    for sentinel in SENTINELS:
        assert sentinel not in text
        assert sentinel not in envelope


_FREE_TEXT = {
    "oversight": {"entries": 1, "approvals": 1, "resumes": 0, "roles": 1, "notes": "x"},
    "incidents": {
        "open": 1,
        "closed": 0,
        "items": [
            {
                "incident_id": "INC-1",
                "incident_class": "death",
                "status": "open",
                "declared_on": "2026-04-02",
                "aware_on": "2026-04-01",
                "description": "x",
            }
        ],
    },
    "agents": {"agents": 1, "with_mandate": 0, "with_guardrails": 0, "tool_name": "x"},
}


def test_hand_built_free_text_summaries_fail_schema():
    if not SCHEMA.exists():
        pytest.skip(
            "dashboard-saas/schemas/first_scan_status.schema.json not reachable"
        )
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    base = prepare_scan_status_artifact(
        {
            "install_id": "i",
            "system_id": SYS,
            "commit_ref": COMMIT,
            "result": "pass",
            "rationale_hash": "sha256:" + "c" * 64,
            "duration_ms": 1,
        },
        commit_env={},
    )
    validator = jsonschema.Draft202012Validator(schema)
    assert list(validator.iter_errors(base)) == []
    for key, block in _FREE_TEXT.items():
        with pytest.raises(jsonschema.ValidationError):
            validator.validate({**base, "summaries": {key: block}})


@pytest.mark.parametrize("key", list(_FREE_TEXT))
def test_hand_built_free_text_summaries_fail_model(key):
    with pytest.raises(ValidationError, match="Extra inputs"):
        ArtifactSummaries.model_validate({key: _FREE_TEXT[key]})


def test_no_sources_artifact_is_byte_identical(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, agents=False)
    (tmp_path / "repo").mkdir()
    assert _check(tmp_path).exit_code == 0
    first = json.loads(_artifact_text(tmp_path))
    monkeypatch.setattr(main, "with_summaries", lambda artifact, **kw: artifact)
    assert _check(tmp_path).exit_code == 0
    second = json.loads(_artifact_text(tmp_path))
    assert "summaries" not in first
    for volatile in ("timestamp", "duration_ms"):
        first.pop(volatile, None)
        second.pop(volatile, None)
    assert first == second


def test_packs_and_new_summaries_coexist(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _sources(tmp_path)
    pack = build_pack(
        {"points": [{"point": "a", "populated": True, "content": "x"}]},
        system_id=SYS,
        issued_on="2026-10-07",
        generator_version="1",
    )
    pack_dir = tmp_path / "repo" / "deployer-pack"
    pack_dir.mkdir()
    (pack_dir / f"deployer_pack_{pack.integrity.pack_sha256[:12]}.json").write_text(
        pack.model_dump_json(), encoding="utf-8"
    )
    assert _check(tmp_path).exit_code == 0
    s = json.loads(_artifact_text(tmp_path))["summaries"]
    assert s["packs"]["issued"] == 1
    assert s["oversight"]["entries"] == 2


def test_option_paths_override_defaults(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    (tmp_path / "repo").mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    SignedLog(elsewhere / "o.json", SigningDomain.OVERSIGHT_LOG).append(
        {"event": "approval_minted", "system_id": SYS, "role": "R"}, ts=TS
    )
    SignedLog(elsewhere / "a.jsonl", SigningDomain.AGENT_LOG).append(
        {"agent_id": AGENT, "tool": TOOL, "outside_mandate": False}, ts=TS
    )
    reg = incident.IncidentRegister()
    incident.declare(
        reg,
        system_id=SYS,
        declared_at="2026-04-02T08:00:00Z",
        aware_at="2026-04-02T08:00:00Z",
        description=DESC,
    )
    incident.save_register(elsewhere / "r.json", reg)
    result = _check(
        tmp_path,
        "--oversight-log",
        str(elsewhere / "o.json"),
        "--agent-log",
        str(elsewhere / "a.jsonl"),
        "--incident-register",
        str(elsewhere / "r.json"),
    )
    assert result.exit_code == 0, result.output
    s = json.loads(_artifact_text(tmp_path))["summaries"]
    assert s["oversight"]["entries"] == 1
    assert s["agents"]["log_entries"] == 1
    assert s["incidents"]["open"] == 1


def test_corrupt_oversight_log_warns_and_check_still_exits_as_before(
    tmp_path, monkeypatch
):
    _setup(tmp_path, monkeypatch, agents=False)
    (tmp_path / "repo").mkdir()
    before = _check(tmp_path)
    log = tmp_path / "state" / "oversight-log.json"
    log.parent.mkdir(parents=True)
    log.write_text(f"{DESC} not json\n", encoding="utf-8")
    after = _check(tmp_path)
    assert after.exit_code == before.exit_code == 0
    assert "oversight summary omitted (JSONDecodeError)" in after.output
    assert DESC not in after.output
    assert "summaries" not in json.loads(_artifact_text(tmp_path))
