"""`opencomplai gaps --target NIST_AI_RMF` prints a per-subcategory NIST AI
RMF 1.0 profile, re-projected from the same EU AI Act evidence `opencomplai
gaps` already computes (CP-16, D-3c). No new scanner or evaluator involved.
"""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _write_manifest(tmp_path: Path, system_id: str, intended_purpose: str) -> Path:
    manifest_file = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            system_id,
            "--intended-purpose",
            intended_purpose,
            "--output",
            str(manifest_file),
        ],
    )
    assert result.exit_code == 0, f"init failed: {result.output}"
    return manifest_file


def test_target_defaults_to_eu_ai_act_output_unchanged(tmp_path):
    """Byte-for-byte compatibility: omitting --target must not change today's
    default `opencomplai gaps` output."""
    manifest_file = _write_manifest(
        tmp_path, "sys-default-target", "credit scoring for loan applications"
    )
    result = runner.invoke(
        app,
        ["gaps", "--manifest", str(manifest_file), "--repo-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert "Opencomplai Gap Report" in result.output
    assert "NIST AI RMF" not in result.output


def test_target_nist_ai_rmf_prints_subcategory_profile(tmp_path):
    manifest_file = _write_manifest(
        tmp_path, "sys-nist-target", "credit scoring for loan applications"
    )
    result = runner.invoke(
        app,
        [
            "gaps",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(tmp_path),
            "--target",
            "NIST_AI_RMF",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "NIST AI RMF Gap Report" in result.output
    # GOVERN 1.1 must cite Art. 17 (the crosswalk's most direct mapping) as
    # its EU AI Act evidence -- the citation trail the epic's Accept
    # criterion requires.
    assert "GOVERN 1.1" in result.output
    assert "Art. 17" in result.output
    assert "framework crosswalk" in result.output


def test_target_nist_ai_rmf_json_output_carries_citation_trail(tmp_path):
    manifest_file = _write_manifest(
        tmp_path, "sys-nist-json", "credit scoring for loan applications"
    )
    result = runner.invoke(
        app,
        [
            "gaps",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(tmp_path),
            "--target",
            "NIST_AI_RMF",
            "--output",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    nist_report = envelope["payload"]["nist_rmf_report"]
    assert len(nist_report["subcategories"]) == 72

    govern_1_1 = next(
        row
        for row in nist_report["subcategories"]
        if row["subcategory"] == "GOVERN 1.1"
    )
    assert "Art. 17" in govern_1_1["source_eu_ai_act_articles"]
    assert govern_1_1["needs_founder_review"] is True

    # Uncovered function (no crosswalk row maps to MANAGE): unverified, not
    # fabricated.
    manage_1_1 = next(
        row
        for row in nist_report["subcategories"]
        if row["subcategory"] == "MANAGE 1.1"
    )
    assert manage_1_1["status"] == "unverified"
    assert manage_1_1["mapping_confidence"] is None


def test_target_eu_ai_act_json_output_has_no_nist_key(tmp_path):
    """Byte-for-byte compatibility: the default target's JSON payload must
    not gain a new key."""
    manifest_file = _write_manifest(
        tmp_path, "sys-eu-json", "credit scoring for loan applications"
    )
    result = runner.invoke(
        app,
        [
            "gaps",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(tmp_path),
            "--output",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert "nist_rmf_report" not in envelope["payload"]


def _write_manifest_with_target(
    tmp_path: Path, system_id: str, intended_purpose: str, compliance_target: str
) -> Path:
    manifest_file = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            system_id,
            "--intended-purpose",
            intended_purpose,
            "--compliance-target",
            compliance_target,
            "--output",
            str(manifest_file),
        ],
    )
    assert result.exit_code == 0, f"init failed: {result.output}"
    return manifest_file


def test_check_with_gaps_and_nist_target_attaches_nist_rmf_report(
    tmp_path, monkeypatch
):
    """`opencomplai check` also emits the RMF-profile report (task 3) when
    the manifest's compliance_target is NIST_AI_RMF and --with-gaps is set."""
    monkeypatch.chdir(tmp_path)
    manifest_file = _write_manifest_with_target(
        tmp_path, "sys-check-nist", "customer support chatbot", "NIST_AI_RMF"
    )
    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(tmp_path),
            "--with-gaps",
        ],
    )
    assert result.exit_code == 0, result.output

    artifact = json.loads((tmp_path / "compliance-artifact.json").read_text())
    assert artifact["nist_rmf_report"] is not None
    assert len(artifact["nist_rmf_report"]["subcategories"]) == 72


def test_check_with_gaps_and_eu_target_omits_nist_rmf_report(tmp_path, monkeypatch):
    """Default EU_AI_ACT target: no `nist_rmf_report` key change to existing
    `check` behaviour."""
    monkeypatch.chdir(tmp_path)
    manifest_file = _write_manifest(
        tmp_path, "sys-check-eu", "customer support chatbot"
    )
    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest_file),
            "--repo-root",
            str(tmp_path),
            "--with-gaps",
        ],
    )
    assert result.exit_code == 0, result.output

    artifact = json.loads((tmp_path / "compliance-artifact.json").read_text())
    assert artifact["nist_rmf_report"] is None
