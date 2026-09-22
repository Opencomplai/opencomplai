"""`opencomplai gaps` prints a "Mapped" column sourced from the framework
crosswalk (CP-5, D-3a). Mapped only — no computed verdict, see
`opencomplai_core.framework_crosswalk`."""

from __future__ import annotations

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


def test_gaps_table_has_mapped_column_header():
    from opencomplai_core.control_catalog import get_catalog

    # Sanity: the data layer this column reads from is populated (exercised
    # end to end below; this just documents the dependency for a quick read).
    assert get_catalog()["Art. 9"].iso_42001_clause


def test_gaps_human_output_includes_mapped_header_and_iso_clause(tmp_path):
    manifest_file = _write_manifest(
        tmp_path, "sys-mapped", "credit scoring for loan applications"
    )
    result = runner.invoke(
        app,
        ["gaps", "--manifest", str(manifest_file), "--repo-root", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    assert "Mapped" in result.output
    # Art. 9 (risk management system) is a near-certain gap article for this
    # fixture and has a crosswalk row — its ISO/IEC 42001 clause citation
    # ("Clause 6.1") must appear in the printed table.
    assert "Clause 6.1" in result.output
