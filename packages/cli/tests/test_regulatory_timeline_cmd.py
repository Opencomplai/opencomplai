"""Timeline block in `gaps` and `check` human output (SU-11)."""

from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path

from opencomplai_cli import main
from opencomplai_cli.main import app
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import ScanResult, ScanStatusArtifact
from opencomplai_core.regulatory_timeline import load_timeline
from rich.console import Console
from typer.testing import CliRunner

runner = CliRunner()
SOURCE = "Reg. (EU) 2026/1744 (Digital Omnibus), amending Reg. (EU) 2024/1689 Art. 113"


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "sys-tl",
            "--intended-purpose",
            "credit scoring for loan applications",
            "--output",
            str(path),
        ],
    )
    assert result.exit_code == 0, result.output
    return path


def test_gaps_prints_timeline_block(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path)
    buf = io.StringIO()
    monkeypatch.setattr(main, "console", Console(file=buf, width=300))
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app, ["gaps", "--manifest", str(manifest), "--repo-root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    out = result.output + buf.getvalue()
    assert "Regulatory timeline" in out
    # the Art. 6 row implies both Annex dates; the source text is printed verbatim
    assert "2027-12-02" in out
    assert "2028-08-02" in out
    assert f"[{SOURCE}; confidence low; pending founder review]" in out
    assert "date unconfirmed" in out
    assert "(upcoming)" not in out  # dates only, no clock
    assert "(in force)" not in out


def _artifact(with_gaps: bool) -> ScanStatusArtifact:
    gap = build_gap_report("sys-tl", "HEAD", risk_result=None) if with_gaps else None
    return ScanStatusArtifact(
        install_id="install-1",
        system_id="sys-tl",
        commit_ref="HEAD",
        result=ScanResult.PASS,
        rationale_hash="sha256:" + "c" * 64,
        failed_controls=[],
        duration_ms=1,
        gap_report=gap,
    )


def test_check_human_output_shows_timeline(monkeypatch):
    buf = io.StringIO()
    monkeypatch.setattr(main, "console", Console(file=buf, width=300))
    main._print_artifact_human(_artifact(True), today=date(2026, 10, 5))
    out = buf.getvalue()
    assert "Regulatory timeline" in out
    assert "(upcoming)" in out
    assert "(in force)" in out
    assert f"[{SOURCE}; confidence low; pending founder review]" in out

    buf.truncate(0)
    buf.seek(0)
    main._print_artifact_human(_artifact(False), today=date(2026, 10, 5))
    assert "Regulatory timeline" not in buf.getvalue()


def test_check_json_output_unchanged_by_timeline():
    payload = json.loads(_artifact(True).model_dump_json())
    assert "timeline" not in json.dumps(payload).lower()
    assert not any("timeline" in key for key in payload)
    assert load_timeline()  # the data exists, it is just not in the artifact
