"""`opencomplai gaps --map-to DORA|EBA`: opt-in mapped-only citations (SU-32c).
A citation, never a verdict: statuses and the default output must not change."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()
_WIDE = {"COLUMNS": "300"}


def _manifest(tmp_path: Path) -> Path:
    manifest_file = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "sys-map",
            "--intended-purpose",
            "credit scoring for loan applications",
            "--output",
            str(manifest_file),
        ],
    )
    assert result.exit_code == 0, result.output
    return manifest_file


def _gaps(tmp_path: Path, *extra: str, env=None):
    return runner.invoke(
        app,
        [
            "gaps",
            "--manifest",
            str(_manifest_path(tmp_path)),
            "--repo-root",
            str(tmp_path),
            *extra,
        ],
        env=env,
    )


def _manifest_path(tmp_path: Path) -> Path:
    path = tmp_path / "system-manifest.json"
    return path if path.exists() else _manifest(tmp_path)


def _payload(tmp_path: Path, *extra: str) -> dict:
    result = _gaps(tmp_path, "-o", "json", *extra)
    assert result.exit_code == 0, result.output
    return json.loads(result.output)["payload"]


def test_default_gaps_output_unchanged_without_map_to(tmp_path):
    first = _gaps(tmp_path, env=_WIDE)
    again = _gaps(tmp_path, env=_WIDE)
    assert first.exit_code == 0, first.output
    assert first.output == again.output
    assert "(mapped)" not in first.output
    assert "mapped_regimes" not in _gaps(tmp_path, "-o", "json").output


def test_map_to_human_shows_dora_citation(tmp_path):
    result = _gaps(tmp_path, "--map-to", "DORA", env=_WIDE)
    assert result.exit_code == 0, result.output
    assert "Chapter II" in result.output
    assert "Mapped only" in result.output


def test_map_to_json_every_row_flagged(tmp_path):
    mapped = _payload(tmp_path, "--map-to", "DORA", "--map-to", "EBA")["mapped_regimes"]
    assert set(mapped) == {"DORA", "EBA"}
    rows = [r for by_art in mapped.values() for rs in by_art.values() for r in rs]
    assert rows
    for row in rows:
        assert row["needs_founder_review"] is True
        assert row["confidence"] == "low"
        assert row["source"]
        assert row["citation"]
        assert "status" not in row


def test_map_to_does_not_change_verdicts(tmp_path):
    base = _payload(tmp_path)
    mapped = _payload(tmp_path, "--map-to", "DORA", "--map-to", "EBA")
    assert mapped["articles"] == base["articles"]
    assert mapped["principle_summary"] == base["principle_summary"]
    assert "mapped_regimes" not in base


def test_map_to_unknown_regime_exits_2(tmp_path):
    result = _gaps(tmp_path, "--map-to", "SOX")
    assert result.exit_code == 2
    assert "DORA" in result.output


def test_map_to_repeatable_and_case_insensitive(tmp_path):
    mapped = _payload(
        tmp_path, "--map-to", "dora", "--map-to", "Eba", "--map-to", "DORA"
    )
    assert set(mapped["mapped_regimes"]) == {"DORA", "EBA"}
