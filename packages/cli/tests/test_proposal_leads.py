"""Annex III area leads in scan, scan --quick and check --scan output."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest
from opencomplai_cli import leads, main
from opencomplai_cli.main import FailOnLevel, _scan_should_fail, app
from opencomplai_core.models import (
    CorroborationReport,
    EuAiProposalLead,
    EuAiScanSummary,
    SystemManifest,
)
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()

_HINT = "pip install opencomplai-ai"
_HEADING = "Annex III area leads (for a person to review, not findings)"
# area -> (code signal of the knowledge pack, person-cue argument, area label)
_SIGNALS = {
    3: ("auto_grade", "grades", "3 Education"),
    4: ("rank_candidates", "applicants", "4 Employment"),
    5: ("credit_score", "customer", "5 Essential services"),
    6: ("recidivism_score", "defendant", "6 Law enforcement"),
    7: ("visa_score", "applicant", "7 Migration"),
    8: ("voter_target", "voters", "8 Justice & democracy"),
}


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _program(signal: str, arg: str) -> str:
    return (
        "from sklearn.ensemble import RandomForestClassifier\n\n\n"
        f"def run({arg}):\n    result = {signal}({arg})\n    return result\n"
    )


@pytest.fixture(autouse=True)
def _leads_policy(monkeypatch):
    """Keep these tests about the mechanism, whatever policy values ship."""
    monkeypatch.setattr(leads, "LEADS_DEFAULT_ON", True)
    monkeypatch.setattr(leads, "NOTICE_ONLY_AREAS", frozenset())
    monkeypatch.delenv("OPENCOMPLAI_LEADS", raising=False)


def _env(tmp_path: Path, monkeypatch, areas=tuple(_SIGNALS), face=False):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    monkeypatch.delenv("OPENCOMPLAI_VAULT_URL", raising=False)
    monkeypatch.delenv("SIGNING_KEY_PRIVATE", raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    key_dir = tmp_path / "keys"
    generate_keypair(key_dir)
    monkeypatch.setattr(main, "_SIGNING_KEY", key_dir / "signing.key")
    manifest = tmp_path / "system-manifest.json"
    manifest.write_text(
        SystemManifest(
            system_id="lead-sys",
            intended_purpose="customer support chatbot",
            compliance_target="EU_AI_ACT",
            high_risk_presumption=False,
            commit_ref="HEAD",
        ).model_dump_json(),
        encoding="utf-8",
    )
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    for area in areas:
        signal, arg, _ = _SIGNALS[area]
        (repo / "src" / f"a{area}.py").write_text(
            _program(signal, arg), encoding="utf-8"
        )
    if face:
        (repo / "face.py").write_text("import face_recognition\n", encoding="utf-8")
    return manifest, repo


def _scan(manifest: Path, repo: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--no-emit-evidence",
            "--no-ocignore-bootstrap",
            *extra,
        ],
    )


def _check(manifest: Path, repo: Path, *extra: str):
    return runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--scan",
            *extra,
        ],
    )


def _hint_lines(text: str) -> int:
    return sum(1 for ln in text.splitlines() if _HINT in ln)


def _assert_lead_lines(output: str, areas) -> None:
    flat = _flat(output)
    assert _HEADING in flat
    for area in areas:
        signal, _, label = _SIGNALS[area]
        assert f"src/a{area}.py:5 {signal} {label} " in flat, (area, flat)
    assert "lowest confidence" in flat
    assert "not a finding" in flat


def _runs(manifest: Path, repo: Path, out: Path):
    """scan, scan --quick and check --scan, with --fail-on major."""
    return {
        "scan": _scan(manifest, repo, "--fail-on", "major"),
        "quick": _scan(manifest, repo, "--quick"),
        "check": _check(manifest, repo, "--output-dir", str(out)),
    }


def test_leads_shown_and_exit_code_unchanged(tmp_path, monkeypatch):
    pytest.importorskip("opencomplai_ai")
    manifest, repo = _env(tmp_path, monkeypatch, face=True)
    with_plugin = _runs(manifest, repo, tmp_path / "out_with")
    for name, result in with_plugin.items():
        assert result.exit_code in (0, 1), (name, result.output)
        _assert_lead_lines(result.stdout, _SIGNALS)
    sidecar = json.loads(
        (tmp_path / "out_with" / "scan-report.json").read_text(encoding="utf-8")
    )
    block = sidecar["eu_ai_scan"]["proposal_leads"]
    assert sorted(x["annex_iii_area"] for x in block) == sorted(_SIGNALS)
    assert {x["reason"] for x in block} == {"deterministic_matcher"}
    assert {x["annex_iii_area"]: x["confidence_band"] for x in block}[5] == "low"
    as_json = _scan(manifest, repo, "-o", "json")
    with_payload = json.loads(as_json.stdout)["payload"]
    assert len(with_payload["eu_ai_scan"]["proposal_leads"]) == 6

    monkeypatch.setitem(sys.modules, "opencomplai_ai", None)
    without = _runs(manifest, repo, tmp_path / "out_without")
    without_payload = json.loads(_scan(manifest, repo, "-o", "json").stdout)["payload"]
    for name in with_plugin:
        assert with_plugin[name].exit_code == without[name].exit_code, name
        assert _HEADING not in without[name].stdout, name
    assert with_plugin["scan"].exit_code == 1, "fixture must make the gate bite"
    for key in ("severity", "discrepancies", "report_hash", "detected_categories"):
        assert with_payload[key] == without_payload[key], key
    assert without_payload.get("eu_ai_scan") is None


def test_quick_scan_shows_leads(tmp_path, monkeypatch):
    pytest.importorskip("opencomplai_ai")
    manifest, repo = _env(tmp_path, monkeypatch, areas=(4,))
    result = _scan(manifest, repo, "--quick")
    assert result.exit_code == 0, result.output
    flat = _flat(result.stdout)
    assert _HEADING in flat
    assert "src/a4.py:5 rank_candidates 4 Employment medium" in flat
    # the leads come before the quick scan's own closing block
    assert flat.index(_HEADING) < flat.index("Discovery only")


def test_check_scan_shows_leads_and_sidecar(tmp_path, monkeypatch):
    pytest.importorskip("opencomplai_ai")
    manifest, repo = _env(tmp_path, monkeypatch, areas=(4, 7))
    out = tmp_path / "out"
    result = _check(manifest, repo, "--output-dir", str(out))
    assert result.exit_code == 0, result.output
    flat = _flat(result.stdout)
    assert _HEADING in flat
    assert "src/a4.py:5 rank_candidates 4 Employment medium" in flat
    assert "src/a7.py:5 visa_score 7 Migration medium" in flat
    # printed after the artifact, before the coverage notice
    assert flat.index("Artifact written") < flat.index(_HEADING)
    assert flat.index(_HEADING) < flat.index("What the default scan covers")
    sidecar = json.loads((out / "scan-report.json").read_text(encoding="utf-8"))
    entries = sidecar["eu_ai_scan"]["proposal_leads"]
    assert [(e["file"], e["line"], e["annex_iii_area"]) for e in entries] == [
        ("src/a4.py", 5, 4),
        ("src/a7.py", 5, 7),
    ]
    assert sidecar["eu_ai_scan"]["regulatory_finding_count"] == 0


def test_plugin_absent_prints_one_hint_line(tmp_path, monkeypatch):
    manifest, repo = _env(tmp_path, monkeypatch, areas=(4,))
    monkeypatch.setitem(sys.modules, "opencomplai_ai", None)
    for name, result in {
        "scan": _scan(manifest, repo),
        "quick": _scan(manifest, repo, "--quick"),
        "check": _check(manifest, repo, "--output-dir", str(tmp_path / "out")),
    }.items():
        assert result.exit_code == 0, (name, result.output)
        assert _hint_lines(result.stderr) == 1, (name, result.stderr)
        assert _hint_lines(result.stdout) == 0, name
        assert _HEADING not in result.stdout, name


def test_hint_not_printed_when_findings_replace_leads(tmp_path, monkeypatch):
    manifest, repo = _env(tmp_path, monkeypatch, areas=(4,))
    monkeypatch.setitem(sys.modules, "opencomplai_ai", None)
    result = _scan(manifest, repo, "--ai-intent")
    assert _hint_lines(result.stderr) == 0


def test_hint_not_printed_when_intent_analysis_skipped(tmp_path, monkeypatch):
    manifest, repo = _env(tmp_path, monkeypatch, areas=(4,))
    monkeypatch.setitem(sys.modules, "llama_cpp", None)
    # the CI shape: the intent analysis degrades to skipped, plugin leads absent
    monkeypatch.setattr(main, "_preload_ai_model", lambda _model: False)
    monkeypatch.setattr(leads, "plugin_installed", lambda: False)
    result = _scan(manifest, repo, "--ai-intent")
    assert _hint_lines(result.stderr) == 0, result.stderr


def test_signed_artifact_has_no_lead(tmp_path, monkeypatch):
    pytest.importorskip("opencomplai_ai")
    manifest, repo = _env(tmp_path, monkeypatch, areas=(4,))
    out = tmp_path / "out"
    result = _check(manifest, repo, "--output-dir", str(out))
    assert result.exit_code == 0, result.output
    artifact_text = (out / "compliance-artifact.json").read_text(encoding="utf-8")
    for needle in (
        "proposal_leads",
        "confidence_band",
        "src/a4.py:5",
        "deterministic_matcher",
        "rank_candidates",
    ):
        assert needle not in artifact_text, needle
    sidecar = out / "scan-report.json"
    assert "proposal_leads" in sidecar.read_text(encoding="utf-8")
    # the sidecar is an input of the artifact like any other field: one digest
    digest = (
        "sha256:"
        + hashlib.sha256(sidecar.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    )
    assert digest in json.loads(artifact_text)["evidence_hashes"]


def test_json_stdout_stays_clean(tmp_path, monkeypatch):
    pytest.importorskip("opencomplai_ai")
    manifest, repo = _env(tmp_path, monkeypatch, areas=(4,))
    result = _scan(manifest, repo, "-o", "json")
    assert result.exit_code == 0, result.output
    assert _HEADING not in result.stdout
    leads_block = json.loads(result.stdout)["payload"]["eu_ai_scan"]["proposal_leads"]
    assert [x["annex_iii_area"] for x in leads_block] == [4]
    monkeypatch.setitem(sys.modules, "opencomplai_ai", None)
    absent = _scan(manifest, repo, "-o", "json")
    assert _hint_lines(absent.stdout) == 0
    assert _hint_lines(absent.stderr) == 1
    assert json.loads(absent.stdout)["payload"].get("eu_ai_scan") is None


def _hand_report(severity: str, n_leads: int, **extra) -> CorroborationReport:
    summary = EuAiScanSummary(
        proposal_leads=[
            EuAiProposalLead(
                file=f"src/m{i}.py",
                line=i + 1,
                function="rank_candidates",
                annex_iii_area=4,
                confidence_band="medium",
                signals=["rank_candidates"],
            )
            for i in range(n_leads)
        ]
    )
    return CorroborationReport.model_validate(
        {
            "scan_id": "scan-1",
            "system_id": "test-sys",
            "commit_ref": "HEAD",
            "scanner_version": "0.1.0",
            "input_digest": "sha256:abc",
            "config_hash": "sha256:def",
            "detector_versions": {},
            "declared_purpose": "customer support chatbot",
            "declared_categories": [],
            "evidence": [],
            "findings": [],
            "detected_categories": [],
            "discrepancies": ["scoring_profiling"] if severity != "none" else [],
            "score_breakdown": {},
            "severity": severity,
            "feature_summary": {},
            "cache_summary": {},
            "skipped_paths": [],
            "limits_hit": [],
            "warnings": [],
            "detector_errors": [],
            "baseline_ref": None,
            "generated_at": "2026-07-11T00:00:00Z",
            "report_hash": "sha256:ghi",
            "eu_ai_scan": summary.model_dump(),
            **extra,
        }
    )


def test_leads_never_gate_fail_on(tmp_path, monkeypatch):
    for level in FailOnLevel:
        for severity in ("none", "major"):
            assert _scan_should_fail(
                _hand_report(severity, 5), level, None
            ) == _scan_should_fail(_hand_report(severity, 0), level, None), (
                level,
                severity,
            )
    # an incomplete scan still fails, with or without leads
    assert _scan_should_fail(
        _hand_report("none", 5, scan_errors=["limit"]), FailOnLevel.none, None
    )

    pytest.importorskip("opencomplai_ai")
    manifest, repo = _env(tmp_path, monkeypatch, areas=(4, 5, 7))
    result = _scan(manifest, repo, "--fail-on", "critical")
    assert result.exit_code == 0, result.output
    assert _HEADING in _flat(result.stdout)
    result = _check(manifest, repo, "--output-dir", str(tmp_path / "out"))
    assert result.exit_code == 0, result.output
    assert _HEADING in _flat(result.stdout)


def test_render_nothing_without_leads():
    from io import StringIO

    from rich.console import Console

    buf = StringIO()
    console = Console(file=buf, width=200)
    leads.render_leads(console, _hand_report("none", 0), main._INTENT_AREA_LABELS)
    plain = _hand_report("none", 0).model_copy(update={"eu_ai_scan": None})
    leads.render_leads(console, plain, main._INTENT_AREA_LABELS)
    assert buf.getvalue() == ""
    leads.render_leads(
        console, _hand_report("none", 12), main._INTENT_AREA_LABELS, limit=10
    )
    out = buf.getvalue()
    assert out.count("rank_candidates") == 10
    assert "... and 2 more" in out
    assert leads.PROPOSAL_LEAD_NOTE in _flat(out)


def test_policy_seam_values(monkeypatch):
    assert leads.INSTALL_HINT.count(_HINT) == 1
    assert "\n" not in leads.INSTALL_HINT
    assert leads.LEADS_DEFAULT_ON is True
    assert leads.NOTICE_ONLY_AREAS == frozenset()
    if leads.plugin_installed():
        assert leads.lead_areas(False, False, False) == frozenset(range(3, 9))
        monkeypatch.setattr(leads, "NOTICE_ONLY_AREAS", frozenset({5}))
        assert 5 not in leads.lead_areas(False, False, False)
    for flags in ((True, False, False), (False, True, False), (False, False, True)):
        assert leads.lead_areas(*flags) == frozenset()
        assert leads.want_leads(*flags) is False
    monkeypatch.setattr(leads, "LEADS_DEFAULT_ON", False)
    assert leads.want_leads(False, False, False) is False
    assert leads.lead_areas(False, False, False) == frozenset()
