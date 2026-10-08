"""CLI tests for `opencomplai qms generate --manifest` (SU-24a2)."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _run(tmp_path: Path, *extra: str):
    out = tmp_path / "qms.md"
    result = runner.invoke(
        app,
        [
            "qms",
            "generate",
            "--repo-root",
            str(tmp_path),
            "--output",
            str(out),
            "--scan-report",
            str(tmp_path / "scan-report.json"),
            "--eval-report",
            str(tmp_path / "eval-report.json"),
            *extra,
        ],
    )
    return result, out


def _manifest(tmp_path: Path, **kw: object) -> Path:
    path = tmp_path / "system-manifest.json"
    path.write_text(
        json.dumps({"system_id": "s", "intended_purpose": "scoring", **kw}),
        encoding="utf-8",
    )
    return path


def test_manifest_fills_e_h_i(tmp_path: Path) -> None:
    manifest = _manifest(
        tmp_path,
        harmonised_standards=["EN 18286"],
        alternative_solutions="in-house controls",
        post_market_monitoring_plan_ref="docs/pmm.md",
        incident_response_procedure="page the on-call lead",
    )
    result, _ = _run(tmp_path, "-m", str(manifest), "--output-format", "json")
    assert result.exit_code == 0, result.output
    rows = {c["clause"]: c for c in json.loads(result.output)["clauses"]}
    assert "EN 18286" in rows["Art. 17(1)(e)"]["manifest_content"]
    assert "in-house controls" in rows["Art. 17(1)(e)"]["manifest_content"]
    assert rows["Art. 17(1)(h)"]["manifest_content"] == "docs/pmm.md"
    assert rows["Art. 17(1)(i)"]["manifest_content"] == "page the on-call lead"
    assert rows["Art. 17(1)(a)"]["manifest_content"] == ""
    md = (tmp_path / "qms.md").read_text(encoding="utf-8")
    assert "page the on-call lead" in md
    assert "Manifest-declared" in md


def test_missing_manifest_exits_2(tmp_path: Path) -> None:
    result, _ = _run(tmp_path, "-m", str(tmp_path / "nope.json"))
    assert result.exit_code == 2


def test_no_manifest_output_unchanged(tmp_path: Path) -> None:
    result, out = _run(tmp_path)
    assert result.exit_code == 0, result.output
    md = out.read_text(encoding="utf-8")
    assert "Manifest-declared" not in md
    assert md.count("| Missing |") == 13
    assert "Profile notes" not in md


def test_micro_manifest_note_in_cli_output(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, organisation_size="micro")
    result, out = _run(tmp_path, "-m", str(manifest))
    assert result.exit_code == 0, result.output
    assert "microenterprises" in result.output
    assert "needs founder review" in out.read_text(encoding="utf-8")
    small = _manifest(tmp_path, organisation_size="small")
    result, _ = _run(tmp_path, "-m", str(small))
    assert "microenterprises" not in result.output


def test_docs_pages_are_in_nav() -> None:
    root = Path(__file__).resolve().parents[3]
    nav = (root / "docs" / "mkdocs.yml").read_text(encoding="utf-8")
    for name in ("qms", "fria"):
        assert f"- {name}: cli/{name}.md" in nav
        assert (root / "docs" / "src" / "cli" / f"{name}.md").is_file()
