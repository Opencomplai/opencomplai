"""`recommend --gap-report` and `report --gap-report` accept what
`opencomplai gaps --output json` prints: the ScanOutputEnvelope with the
GapReport under `payload`, including the UTF-16LE-with-BOM file a Windows
PowerShell 5.1 `>` redirect writes and the ANSI code page (cp1252) file a
cmd.exe or Git Bash redirect writes. A bare GapReport JSON still works.
"""

from __future__ import annotations

import codecs
import json
import locale
from pathlib import Path

import pytest
from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


def _utf8(text: str) -> bytes:
    return text.encode("utf-8")


def _utf16_le_bom(text: str) -> bytes:
    return codecs.BOM_UTF16_LE + text.encode("utf-16-le")


def _bare_gap_report(text: str) -> bytes:
    return json.dumps(json.loads(text)["payload"]).encode("utf-8")


def _cp1252_em_dash(text: str) -> bytes:
    # gap_probes rationales carry an em dash, which cp1252 writes as 0x97
    envelope = json.loads(text)
    rationale = "Heuristic only — not a full obligation assessment."
    envelope["payload"]["articles"][0]["rationale"] = rationale
    return json.dumps(envelope, ensure_ascii=False).encode("cp1252")


@pytest.mark.parametrize(
    ("gaps_args", "encode"),
    [
        ([], _utf8),
        ([], _utf16_le_bom),
        ([], _bare_gap_report),
        ([], _cp1252_em_dash),
        # payload carries an extra nist_rmf_report key next to the GapReport
        (["--target", "NIST_AI_RMF"], _utf8),
    ],
    ids=[
        "envelope-utf8",
        "envelope-utf16-bom",
        "bare-gap-report",
        "envelope-cp1252",
        "envelope-nist",
    ],
)
def test_gaps_json_output_feeds_recommend_and_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gaps_args, encode
) -> None:
    monkeypatch.chdir(tmp_path)
    # a Windows ANSI code page locale, whatever OS runs the test
    monkeypatch.setattr(locale, "getpreferredencoding", lambda _=True: "cp1252")
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "gap-input",
            "--intended-purpose",
            "credit scoring for loan applications",
        ],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(app, ["gaps", "--output", "json", *gaps_args])
    assert result.exit_code == 0, result.output
    gap_file = tmp_path / "gap-report.json"
    gap_file.write_bytes(encode(result.stdout))

    result = runner.invoke(
        app, ["recommend", "--gap-report", str(gap_file), "--output", "fixes"]
    )
    assert result.exit_code == 0, result.output
    assert "remediation template(s)" in result.output
    assert any((tmp_path / "fixes").iterdir())

    result = runner.invoke(
        app, ["report", "--gap-report", str(gap_file), "--output", "report.html"]
    )
    assert result.exit_code == 0, result.output
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "No gap report supplied" not in html
    assert "Art. 6" in html
