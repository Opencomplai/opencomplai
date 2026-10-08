"""SU-21b: the Art. 13 deployer_instructions probe checks Art. 13(3) topic markers."""

from __future__ import annotations

from pathlib import Path

from opencomplai_core.gap_probes import artifact_gap_status
from opencomplai_core.instructions_for_use import (
    generate_instructions_for_use,
    render_instructions_for_use_markdown,
)
from opencomplai_core.models import GapStatus, SystemManifest


def test_bare_instructions_file_is_low_confidence_partial(tmp_path: Path):
    (tmp_path / "INSTRUCTIONS.md").write_text(
        "# Instructions\n\nTODO\n", encoding="utf-8"
    )
    row = artifact_gap_status("deployer_instructions", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == 0.35
    assert "Art. 13(3) topic" in row.rationale


def test_instructions_with_content_markers_is_higher_confidence_partial(
    tmp_path: Path,
):
    (tmp_path / "INSTRUCTIONS.md").write_text(
        "The intended purpose is credit scoring. Human oversight: a reviewer "
        "confirms every denial.\n",
        encoding="utf-8",
    )
    row = artifact_gap_status("deployer_instructions", tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.status != GapStatus.MET
    assert row.confidence == 0.6
    assert "Art. 13(3) topic markers" in row.rationale


def test_missing_instructions_still_missing(tmp_path: Path):
    row = artifact_gap_status("deployer_instructions", tmp_path)
    assert row.status == GapStatus.MISSING


def test_generated_instructions_markdown_satisfies_markers(tmp_path: Path):
    manifest = SystemManifest(
        system_id="s", intended_purpose="credit scoring", commit_ref="abc"
    )
    doc = generate_instructions_for_use(manifest, generated_at="2026-10-07T00:00:00Z")
    target = tmp_path / "docs" / "instructions.md"
    target.parent.mkdir()
    target.write_text(render_instructions_for_use_markdown(doc), encoding="utf-8")
    row = artifact_gap_status("deployer_instructions", tmp_path)
    assert row.confidence == 0.6
