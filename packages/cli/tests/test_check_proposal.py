"""`check --scan` reads a confirmed classification proposal (CL-C4).

A signed, confirmed proposal that names an Annex III area the declared purpose
does not cover adds one `confirmed_proposal:<area>` row and counts as MAJOR for
`--fail-on`. Absent, unconfirmed, edited or stale proposals change nothing.
Everything is offline and runs under tmp_path.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_cli.inputs import load_manifest
from opencomplai_cli.main import app
from opencomplai_cli.proposal_gate import (
    apply_confirmed_proposal,
    confirmed_proposal_area,
)
from opencomplai_core import rules
from opencomplai_core.classification_proposal import (
    PROPOSAL_FILENAME,
    build_proposal_document,
    proposal_digest,
)
from opencomplai_core.control_identity import fingerprint_manifest
from opencomplai_core.models import (
    CorroborationReport,
    DiscrepancySeverity,
    ScanSummary,
    SignalCategory,
)
from opencomplai_core.scanner.mapping import signal_category_to_taxonomy
from opencomplai_core.signing import generate_keypair
from typer.testing import CliRunner

runner = CliRunner()
PURPOSE = "customer support chatbot"
EMPLOYMENT_PURPOSE = "screening job applicants for recruitment"


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch) -> None:
    """Own cwd, state dir and HOME; no signing key or API anywhere."""
    monkeypatch.chdir(tmp_path)
    for var in (
        "SIGNING_KEY_PRIVATE",
        "OPENCOMPLAI_TRUSTED_KEY_IDS",
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "OPENCOMPLAI_RISK_ENGINE_URL",
        "GITHUB_SHA",
        "CI_COMMIT_SHA",
    ):
        monkeypatch.delenv(var, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home / "missing")
    monkeypatch.setattr(main, "_CONFIG_FILE", home / "missing" / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", home / "missing" / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", home / "missing" / "signing.pub")


def _manifest(tmp_path: Path, purpose: str = PURPOSE) -> Path:
    path = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "prop-sys",
            "--intended-purpose",
            purpose,
            "--output",
            str(path),
        ],
    )
    assert result.exit_code == 0, result.output
    return path


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('hello')\n", encoding="utf-8")
    return repo


def _write_proposal(repo: Path, manifest_path: Path, area: int = 4) -> Path:
    manifest = load_manifest(manifest_path)
    doc = build_proposal_document(
        system_id=manifest.system_id,
        commit_ref="HEAD",
        scanner_version="0.0.0",
        scan_input_digest="sha256:" + "ab" * 32,
        scan_report_hash="sha256:" + "cd" * 32,
        manifest_fingerprint=fingerprint_manifest(manifest),
        declared_purpose=manifest.intended_purpose,
        area="employment",
        confidence="medium",
        evidence=[{"location": "src/a.py:5", "file": "src/a.py", "line": 5}],
        minority_evidence=[],
        prohibited_signals=[],
        proposal={"proposed_annex_iii_area": area, "proposed_area_name": "employment"},
    )
    path = repo / PROPOSAL_FILENAME
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _confirm(tmp_path: Path, repo: Path, manifest_path: Path, proposal: Path) -> None:
    """Confirm with the real `accept --proposal --yes`; never a hand-built record."""
    generate_keypair(tmp_path / "keys")
    result = runner.invoke(
        app,
        [
            "accept",
            "--manifest",
            str(manifest_path),
            "--accepted-by",
            "dpo@example.test",
            "--repo-root",
            str(repo),
            "--proposal",
            str(proposal),
            "--yes",
            "--key",
            str(tmp_path / "keys" / "signing.key"),
        ],
    )
    assert result.exit_code == 0, result.output


def _confirmed(tmp_path: Path, repo: Path, manifest_path: Path, area: int = 4) -> Path:
    proposal = _write_proposal(repo, manifest_path, area)
    _confirm(tmp_path, repo, manifest_path, proposal)
    return proposal


def _check(
    tmp_path: Path, manifest_path: Path, repo: Path, *extra: str, out: str = "out"
) -> tuple[int, dict, Path]:
    out_dir = tmp_path / out
    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_path),
            "--repo-root",
            str(repo),
            "--output-dir",
            str(out_dir),
            *extra,
        ],
    )
    assert result.exit_code in (0, 1), result.output
    artifact = json.loads(
        (out_dir / "compliance-artifact.json").read_text(encoding="utf-8")
    )
    return result.exit_code, artifact, out_dir


def _outcome(artifact: dict) -> tuple:
    return (
        artifact["result"],
        artifact["failed_controls"],
        artifact["scan_summary"],
    )


def test_check_no_proposal_unchanged(tmp_path: Path) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    code, artifact, _ = _check(tmp_path, manifest, repo, "--scan", "--fail-on", "major")
    assert code == 0
    assert artifact["result"] == "pass"
    assert artifact["scan_summary"]["discrepancies"] == []
    assert artifact["scan_summary"]["severity"] == "none"
    assert "CODE_CORROBORATION_GAP" not in artifact["failed_controls"]


def test_check_unconfirmed_proposal_unchanged(tmp_path: Path) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    args = ("--scan", "--fail-on", "major")
    proposal = _write_proposal(repo, manifest)  # file present, no record at all
    code, baseline, _ = _check(tmp_path, manifest, repo, *args, out="a")
    assert code == 0
    assert baseline["scan_summary"]["discrepancies"] == []

    # A record exists, then the proposal is replaced by a self-consistent one
    # (valid digest, other area): the record no longer matches the file.
    _confirm(tmp_path, repo, manifest, proposal)
    doc = json.loads(proposal.read_text(encoding="utf-8"))
    doc["proposal"]["proposed_annex_iii_area"] = 1
    doc["proposal_sha256"] = proposal_digest(doc)
    proposal.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    code, edited, _ = _check(tmp_path, manifest, repo, *args, out="b")
    assert code == 0
    assert edited["scan_summary"]["discrepancies"] == []
    assert _outcome(edited)[:2] == _outcome(baseline)[:2]

    # A plain edit without a new digest is caught as well.
    doc["area"] = "biometrics"
    proposal.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    code, plain, _ = _check(tmp_path, manifest, repo, *args, out="c")
    assert code == 0
    assert plain["scan_summary"]["discrepancies"] == []

    # A confirmed proposal, then the manifest changes: the record is stale.
    _confirmed(tmp_path, repo, manifest)
    code, _, _ = _check(tmp_path, manifest, repo, *args, out="d")
    assert code == 1  # sanity: this one is confirmed and does disagree
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(PURPOSE, "internal meeting notes"),
        encoding="utf-8",
    )
    assert PURPOSE not in manifest.read_text(encoding="utf-8")
    code, stale, _ = _check(tmp_path, manifest, repo, *args, out="e")
    assert code == 0
    assert stale["scan_summary"]["discrepancies"] == []
    assert stale["scan_summary"]["severity"] == "none"
    assert confirmed_proposal_area(load_manifest(manifest), repo) is None


def test_check_confirmed_disagreement_adds_row(tmp_path: Path, monkeypatch) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    _confirmed(tmp_path, repo, manifest)
    assert confirmed_proposal_area(load_manifest(manifest), repo) == 4
    # The record file is part of the scanned tree, so the baseline is the very
    # same tree with the gate switched off, not a tree without the record.
    with monkeypatch.context() as patch:
        patch.setattr(
            "opencomplai_cli.proposal_gate.confirmed_proposal_area",
            lambda *a, **k: None,
        )
        _, before, before_dir = _check(tmp_path, manifest, repo, "--scan", out="a")
    assert before["scan_summary"]["discrepancies"] == []

    _, after, after_dir = _check(tmp_path, manifest, repo, "--scan", out="b")
    summary = after["scan_summary"]
    assert "confirmed_proposal:employment" in summary["discrepancies"]
    assert summary["severity"] == "major"
    # D4: the report, its hash and the sidecar stay as scanned. The cache
    # counters (warm second run) and the timestamp are outside the hash.
    before_report = json.loads((before_dir / "scan-report.json").read_text("utf-8"))
    sidecar = json.loads((after_dir / "scan-report.json").read_text("utf-8"))
    for volatile in ("cache_summary", "generated_at"):
        before_report.pop(volatile)
        sidecar.pop(volatile)
    assert sidecar == before_report
    assert "confirmed_proposal:employment" not in sidecar["discrepancies"]
    assert sidecar["severity"] == "none"
    assert summary["report_hash"] == before["scan_summary"]["report_hash"]


@pytest.mark.parametrize(
    ("level", "baseline", "exit_code"),
    [
        ("none", None, 0),
        ("critical", None, 0),
        ("major", None, 1),
        ("new-major", None, 1),
        ("new-major", ["employment"], 0),
    ],
)
def test_check_confirmed_disagreement_fail_on_levels(
    tmp_path: Path, level: str, baseline: list[str] | None, exit_code: int
) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    _confirmed(tmp_path, repo, manifest)
    extra = ["--scan", "--fail-on", level]
    if baseline is not None:
        base = tmp_path / "baseline.json"
        base.write_text(json.dumps({"accepted_categories": baseline}), encoding="utf-8")
        extra += ["--baseline", str(base)]
    code, artifact, _ = _check(tmp_path, manifest, repo, *extra)
    assert code == exit_code
    failed = "CODE_CORROBORATION_GAP" in artifact["failed_controls"]
    assert failed is (exit_code == 1)
    assert (artifact["result"] == "pass") is (exit_code == 0)


def test_check_confirmed_agreement_unchanged(tmp_path: Path) -> None:
    manifest, repo = _manifest(tmp_path, EMPLOYMENT_PURPOSE), _repo(tmp_path)
    args = ("--scan", "--fail-on", "major")
    # A recruitment purpose is high-risk on its own: compare, do not assume exit 0.
    code, plain, _ = _check(tmp_path, manifest, repo, *args, out="a")
    _confirmed(tmp_path, repo, manifest)
    assert confirmed_proposal_area(load_manifest(manifest), repo) == 4
    after_code, agreed, _ = _check(tmp_path, manifest, repo, *args, out="b")
    assert after_code == code
    assert agreed["scan_summary"]["discrepancies"] == []
    assert _outcome(agreed)[:2] == _outcome(plain)[:2]
    assert agreed["scan_summary"]["severity"] == plain["scan_summary"]["severity"]


def test_check_proposal_ignored_without_scan(tmp_path: Path) -> None:
    manifest, repo = _manifest(tmp_path), _repo(tmp_path)
    code, plain, _ = _check(tmp_path, manifest, repo, out="a")
    _confirmed(tmp_path, repo, manifest)
    code2, artifact, _ = _check(tmp_path, manifest, repo, out="b")
    assert code2 == code == 0
    assert artifact["scan_summary"] is None
    assert artifact["result"] == plain["result"]
    assert artifact["failed_controls"] == plain["failed_controls"]


def test_proposal_area_keys_are_declared_taxonomy() -> None:
    for area in range(1, 9):
        keys = signal_category_to_taxonomy(
            SignalCategory.SCORING_PROFILING, "", annex_iii_area=area
        )
        assert len(keys) == 1
        assert keys[0] in rules.ANNEX_III_CATEGORIES, (area, keys)


def _summary(severity=DiscrepancySeverity.NONE, discrepancies=()) -> ScanSummary:
    return ScanSummary(
        scan_id="s",
        scanner_version="0",
        severity=severity,
        discrepancies=list(discrepancies),
        report_hash="sha256:" + "0" * 64,
    )


def _report(severity=DiscrepancySeverity.NONE, discrepancies=(), declared=()):
    return CorroborationReport.model_construct(
        declared_categories=list(declared),
        discrepancies=list(discrepancies),
        severity=severity,
    )


def test_apply_confirmed_proposal_pure() -> None:
    summary = _summary(DiscrepancySeverity.MINOR, ["zeta"])
    report = _report(DiscrepancySeverity.MINOR, ["zeta"])
    out_s, out_r = apply_confirmed_proposal(summary, report, 4, None)
    assert out_s.discrepancies == ["zeta", "confirmed_proposal:employment"]
    assert out_r.discrepancies == out_s.discrepancies
    assert out_s.severity == out_r.severity == DiscrepancySeverity.MAJOR
    # Inputs are not mutated.
    assert summary.discrepancies == ["zeta"]
    assert summary.severity == DiscrepancySeverity.MINOR
    assert report.discrepancies == ["zeta"]
    assert report.severity == DiscrepancySeverity.MINOR
    # Idempotent.
    again_s, again_r = apply_confirmed_proposal(out_s, out_r, 4, None)
    assert again_s == out_s
    assert again_r.discrepancies == out_r.discrepancies
    # CRITICAL is never lowered.
    crit_s, crit_r = apply_confirmed_proposal(
        _summary(DiscrepancySeverity.CRITICAL),
        _report(DiscrepancySeverity.CRITICAL),
        4,
        None,
    )
    assert crit_s.severity == crit_r.severity == DiscrepancySeverity.CRITICAL
    # No area, a declared area and a baselined area change nothing.
    assert apply_confirmed_proposal(summary, report, None, None) == (summary, report)
    declared = _report(declared=["employment"])
    assert apply_confirmed_proposal(summary, declared, 4, None) == (summary, declared)
    assert apply_confirmed_proposal(summary, report, 4, ["employment"]) == (
        summary,
        report,
    )
