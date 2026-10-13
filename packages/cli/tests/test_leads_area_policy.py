"""Which Annex III areas may show a lead, and the switch that turns leads off.

The policy values are the measured ones from the benchmark page. They are kept
equal to ``EXPECTED_POLICY`` and ``EXPECTED_LEADS_DEFAULT_ON`` in
``packages/ai/tests/test_leads_benchmark.py``; the two tests are the single
check. These tests run the real path through the CLI runner.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
from opencomplai_cli import leads, main
from opencomplai_cli.main import app
from opencomplai_core.models import SystemManifest
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()

# Kept equal to packages/ai/tests/test_leads_benchmark.py.
EXPECTED_POLICY = {
    3: "lead",
    4: "lead",
    5: "lowest_confidence",
    6: "lead",
    7: "notice_only",
    8: "lead",
}
EXPECTED_LEADS_DEFAULT_ON = True

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
def _no_switch(monkeypatch):
    monkeypatch.delenv("OPENCOMPLAI_LEADS", raising=False)


def _env(tmp_path: Path, monkeypatch, areas=tuple(_SIGNALS)):
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


def _check(manifest: Path, repo: Path, out: Path):
    return runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "--scan",
            "--output-dir",
            str(out),
        ],
    )


def _hint_lines(text: str) -> int:
    return sum(1 for ln in text.splitlines() if _HINT in ln)


def _lead_areas(manifest: Path, repo: Path) -> list[int]:
    result = _scan(manifest, repo, "-o", "json")
    assert result.exit_code in (0, 1), result.output
    summary = json.loads(result.stdout)["payload"].get("eu_ai_scan") or {}
    return sorted(x["annex_iii_area"] for x in summary.get("proposal_leads", []))


def test_constants_match_measured_policy():
    assert leads.NOTICE_ONLY_AREAS == {
        a for a, policy in EXPECTED_POLICY.items() if policy == "notice_only"
    }
    assert leads.LEADS_DEFAULT_ON is EXPECTED_LEADS_DEFAULT_ON
    # area 5 is shown, at the lowest confidence, whatever the floor says
    assert 5 not in leads.NOTICE_ONLY_AREAS
    assert leads.leads_enabled({}) is EXPECTED_LEADS_DEFAULT_ON


def test_notice_only_area_emits_no_lead_and_keeps_exit_code(tmp_path, monkeypatch):
    pytest.importorskip("opencomplai_ai")
    manifest, repo = _env(tmp_path, monkeypatch, areas=(4,))
    monkeypatch.setattr(leads, "NOTICE_ONLY_AREAS", frozenset())
    allowed = _scan(manifest, repo, "--fail-on", "major")
    allowed_check = _check(manifest, repo, tmp_path / "out_allowed")
    allowed_json = json.loads(_scan(manifest, repo, "-o", "json").stdout)["payload"]
    assert _HEADING in _flat(allowed.stdout)
    assert _HEADING in _flat(allowed_check.stdout)

    monkeypatch.setattr(leads, "NOTICE_ONLY_AREAS", frozenset({4}))
    silent = _scan(manifest, repo, "--fail-on", "major")
    silent_check = _check(manifest, repo, tmp_path / "out_silent")
    silent_json = json.loads(_scan(manifest, repo, "-o", "json").stdout)["payload"]
    assert silent.exit_code == allowed.exit_code
    assert silent_check.exit_code == allowed_check.exit_code
    for result in (silent, silent_check):
        assert _HEADING not in _flat(result.stdout)
        assert "rank_candidates 4 Employment" not in _flat(result.stdout)
        assert _hint_lines(result.stderr) == 0
    assert silent_json.get("eu_ai_scan") is None
    for key in ("severity", "discrepancies", "report_hash", "detected_categories"):
        assert silent_json[key] == allowed_json[key], key


def test_area5_is_lowest_confidence_even_below_floor(tmp_path, monkeypatch):
    pytest.importorskip("opencomplai_ai")
    manifest, repo = _env(tmp_path, monkeypatch, areas=(5,))
    assert EXPECTED_POLICY[5] == "lowest_confidence"
    assert 5 not in leads.NOTICE_ONLY_AREAS
    result = _scan(manifest, repo)
    assert result.exit_code == 0, result.output
    flat = _flat(result.stdout)
    assert "src/a5.py:5 credit_score 5 Essential services low lowest confidence" in flat
    block = json.loads(_scan(manifest, repo, "-o", "json").stdout)["payload"][
        "eu_ai_scan"
    ]["proposal_leads"]
    assert [(x["annex_iii_area"], x["confidence_band"]) for x in block] == [(5, "low")]


def test_switch_off_emits_nothing_and_no_hint(tmp_path, monkeypatch):
    pytest.importorskip("opencomplai_ai")
    manifest, repo = _env(tmp_path, monkeypatch, areas=(4,))
    on = _scan(manifest, repo, "--fail-on", "major")
    on_check = _check(manifest, repo, tmp_path / "out_on")
    assert _HEADING in _flat(on.stdout)

    monkeypatch.setenv("OPENCOMPLAI_LEADS", "0")
    off = _scan(manifest, repo, "--fail-on", "major")
    off_check = _check(manifest, repo, tmp_path / "out_off")
    assert off.exit_code == on.exit_code
    assert off_check.exit_code == on_check.exit_code
    for result in (off, off_check):
        assert _HEADING not in _flat(result.stdout)
        assert _hint_lines(result.stdout) == 0
        assert _hint_lines(result.stderr) == 0
    assert _lead_areas(manifest, repo) == []

    # plugin absent and switch off: the install hint is not printed either
    monkeypatch.setitem(sys.modules, "opencomplai_ai", None)
    absent = _scan(manifest, repo)
    assert _hint_lines(absent.stdout) == 0
    assert _hint_lines(absent.stderr) == 0
    monkeypatch.setenv("OPENCOMPLAI_LEADS", "1")
    hinted = _scan(manifest, repo)
    assert _hint_lines(hinted.stderr) == 1


def test_switch_on_emits_leads(tmp_path, monkeypatch):
    pytest.importorskip("opencomplai_ai")
    manifest, repo = _env(tmp_path, monkeypatch, areas=(4,))
    # the switch wins over the shipped default in both directions
    monkeypatch.setattr(leads, "LEADS_DEFAULT_ON", False)
    assert _lead_areas(manifest, repo) == []
    monkeypatch.setenv("OPENCOMPLAI_LEADS", "1")
    result = _scan(manifest, repo)
    assert result.exit_code == 0, result.output
    assert "src/a4.py:5 rank_candidates 4 Employment medium" in _flat(result.stdout)
    assert _lead_areas(manifest, repo) == [4]
    for value in ("true", "ON"):
        monkeypatch.setenv("OPENCOMPLAI_LEADS", value)
        assert leads.leads_enabled() is True
    for value in ("off", "False", "0"):
        monkeypatch.setenv("OPENCOMPLAI_LEADS", value)
        assert leads.leads_enabled() is False
    monkeypatch.setenv("OPENCOMPLAI_LEADS", "maybe")
    assert leads.leads_enabled() is False  # unknown value: the (patched) default


def test_leads_areas_match_benchmark_selection(tmp_path, monkeypatch):
    pytest.importorskip("opencomplai_ai")
    from opencomplai_core.scan_engine import run_scan
    from opencomplai_core.scanner.proposal import build_classification_proposal

    manifest, repo = _env(tmp_path, monkeypatch)
    report = run_scan(
        "lead-sys",
        "HEAD",
        repo,
        "customer support chatbot",
        ai_intent=True,
        ai_model="codebert-onnx",
    )
    assert report.eu_ai_scan is not None
    proposal = build_classification_proposal(report.eu_ai_scan)
    benchmark_areas = {
        ev.annex_iii_area
        for ev in proposal.supporting_evidence + proposal.minority_evidence
        if ev.annex_iii_area in range(3, 9)
    }
    assert benchmark_areas, "the intent scan found no call site"
    assert _lead_areas(manifest, repo) == sorted(
        benchmark_areas - leads.NOTICE_ONLY_AREAS
    )
