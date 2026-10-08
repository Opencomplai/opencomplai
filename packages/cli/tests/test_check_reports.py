"""`check --report-junit / --sarif-output / --summary-md`.

Goldens render the core builders from a static artifact fixture, so later
gap-row changes never churn them; the wiring tests prove the files `check`
writes equal the same builder applied to the written compliance-artifact.json.
"""

from __future__ import annotations

import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import jsonschema
import pytest
from opencomplai_cli import main
from opencomplai_cli.connectors import github_actions
from opencomplai_core import ci_reports
from rich.console import Console

from .test_golden_eu_output import (
    CHATBOT,
    CREDIT,
    _assert_golden,
    _init,
    _normalise,
)
from .test_golden_eu_output import cli as golden_cli  # noqa: F401  (fixture)


@pytest.fixture
def cli(request):
    return request.getfixturevalue("golden_cli")


FIXTURES = Path(__file__).parent / "fixtures"
STATIC = json.loads(
    (FIXTURES / "check_reports_artifact.json").read_text(encoding="utf-8")
)
SCHEMA = json.loads(
    (FIXTURES / "sarif-2.1.0.subset.schema.json").read_text(encoding="utf-8")
)
FLAGS = ("--report-junit", "r.xml", "--sarif-output", "r.sarif", "--summary-md", "r.md")


def _sarif_text(
    artifact: dict, uri: str = "system-manifest.json", version: str = ""
) -> str:
    doc = ci_reports.artifact_to_sarif(artifact, uri, version)
    return json.dumps(doc, indent=2) + "\n"


def _read(name: str) -> str:
    return Path(name).read_bytes().decode("utf-8")


def _check_junit(xml: str, failures: int, errors: int = 0) -> None:
    root = ET.fromstring(xml)
    assert root.tag == "testsuite"
    assert len(root.findall("testcase")) == 1
    assert int(root.get("tests")) == len(root.findall("testcase"))
    assert len(root.findall("testcase/failure")) == failures
    assert len(root.findall("testcase/error")) == errors


def test_report_junit_valid_and_matches_golden(cli, tmp_path):
    golden = ci_reports.artifact_to_junit(STATIC, "see compliance-artifact.json")
    _check_junit(golden, failures=1)
    _assert_golden("check_reports.junit.xml", _normalise(golden, tmp_path))

    _init(cli, CREDIT)
    cli("check", "--with-gaps", *FLAGS, exit_code=1)
    written = _read("r.xml")
    artifact = json.loads(Path("compliance-artifact.json").read_text(encoding="utf-8"))
    assert written == ci_reports.artifact_to_junit(
        artifact, "see compliance-artifact.json"
    )
    _check_junit(written, failures=1)


def test_sarif_output_validates_against_subset_schema(cli, tmp_path):
    golden = _sarif_text(STATIC)
    jsonschema.validate(json.loads(golden), SCHEMA)
    levels = [r["level"] for r in json.loads(golden)["runs"][0]["results"]]
    assert levels == ["error", "error", "error", "warning", "note"]
    _assert_golden("check_reports.sarif.json", _normalise(golden, tmp_path))

    _init(cli, CREDIT)
    cli("check", "--with-gaps", *FLAGS, exit_code=1)
    written = json.loads(_read("r.sarif"))
    jsonschema.validate(written, SCHEMA)
    assert written["runs"][0]["results"]
    artifact = json.loads(Path("compliance-artifact.json").read_text(encoding="utf-8"))
    assert _read("r.sarif") == _sarif_text(
        artifact, "system-manifest.json", main.__version__
    )


def test_summary_md_matches_golden_and_connector(cli, tmp_path):
    golden = ci_reports.artifact_to_summary_md(STATIC) + "\n"
    assert golden.rstrip("\n") == github_actions._build_summary(STATIC, "", "")
    _assert_golden("check_reports.summary.md", _normalise(golden, tmp_path))

    _init(cli, CREDIT)
    cli("check", "--with-gaps", *FLAGS, exit_code=1)
    artifact = json.loads(Path("compliance-artifact.json").read_text(encoding="utf-8"))
    assert _read("r.md") == github_actions._build_summary(artifact, "", "") + "\n"


def test_exit_codes_unchanged_by_report_flags(cli, monkeypatch):
    err = io.StringIO()
    monkeypatch.setattr(
        main, "err_console", Console(file=err, width=200, color_system=None)
    )
    for purpose, target, code in (
        (CHATBOT, "NIST_AI_RMF", 0),
        (CREDIT, "EU_AI_ACT", 1),
    ):
        _init(cli, purpose, target)
        cli("check", "--with-gaps", exit_code=code)
        cli("check", "--with-gaps", *FLAGS, exit_code=code)

    Path("blocker").write_text("a file, not a directory", encoding="utf-8")
    err.seek(0)
    err.truncate()
    cli("check", "--with-gaps", "--report-junit", "blocker/r.xml", exit_code=1)
    assert "WARN" in err.getvalue()
    assert "could not write report" in err.getvalue()
    assert not Path("blocker/r.xml").exists()


def test_flags_absent_writes_nothing(cli):
    _init(cli, CREDIT)
    before = {p.name for p in Path(".").iterdir()}
    cli("check", "--with-gaps", exit_code=1)
    new = {p.name for p in Path(".").iterdir()} - before
    assert not {n for n in new if n.endswith((".xml", ".sarif", ".md"))}


def _record_write_text(monkeypatch) -> list[tuple[str, str | None]]:
    calls: list[tuple[str, str | None]] = []
    orig = Path.write_text

    def rec(self, data, encoding=None, errors=None, newline=None):
        calls.append((self.name, encoding))
        return orig(self, data, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "write_text", rec)
    return calls


def test_check_artifact_written_as_utf8(cli, monkeypatch):
    _init(cli, CREDIT)
    calls = _record_write_text(monkeypatch)
    cli("check", "--with-gaps", exit_code=1)
    assert ("compliance-artifact.json", "utf-8") in calls


def test_sidecar_reports_written_as_utf8(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    text = "café — ok"
    scan, evalr = MagicMock(), MagicMock()
    scan.model_dump_json.return_value = text
    evalr.model_dump_json.return_value = text
    calls = _record_write_text(monkeypatch)
    main._write_sidecar_reports(scan, evalr, quiet=True, output_dir=tmp_path)
    for name in ("scan-report.json", "eval-report.json"):
        assert (tmp_path / name).read_bytes().decode("utf-8") == text
        assert (name, "utf-8") in calls


def _cp1252_default_write(monkeypatch, fail_on: str | None = None):
    """Emulate a legacy locale: write_text without encoding encodes as cp1252."""
    orig = Path.write_text

    def wrapper(self, data, encoding=None, errors=None, newline=None):
        if fail_on and self.name.startswith(fail_on):
            self.touch()  # open('w') truncates before the encode fails
            data = data.encode("cp1252")  # raises UnicodeEncodeError for 'Ł'
        if encoding is None:
            data = data.encode("cp1252").decode("cp1252")
            encoding = "cp1252"
        return orig(self, data, encoding=encoding, errors=errors, newline=newline)

    monkeypatch.setattr(Path, "write_text", wrapper)


def test_init_and_dossier_written_as_utf8(cli, monkeypatch):
    calls = _record_write_text(monkeypatch)
    _init(cli, CREDIT)
    cli(
        "docs",
        "generate",
        "--system-id",
        "golden-sys",
        "--manifest",
        "system-manifest.json",
        "--output-dir",
        ".",
    )
    assert ("system-manifest.json", "utf-8") in calls
    dossiers = [e for n, e in calls if n.startswith("dossier_") and n.endswith(".json")]
    assert dossiers == ["utf-8"]


def test_docs_generate_non_cp1252_provider_exits_zero(cli, monkeypatch):
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    _cp1252_default_write(monkeypatch)
    _init(cli, CREDIT)
    cli(
        "docs",
        "generate",
        "--system-id",
        "golden-sys",
        "--manifest",
        "system-manifest.json",
        "--output-dir",
        ".",
        "--provider-name",
        "Łódź AI",
    )
    (dossier,) = Path(".").glob("dossier_*.json")
    assert "Łódź AI" in dossier.read_bytes().decode("utf-8")


def test_docs_generate_failed_write_leaves_no_dossier(cli, monkeypatch):
    _init(cli, CREDIT)
    _cp1252_default_write(monkeypatch, fail_on="dossier_")
    cli(
        "docs",
        "generate",
        "--system-id",
        "golden-sys",
        "--manifest",
        "system-manifest.json",
        "--output-dir",
        ".",
        "--provider-name",
        "Łódź AI",
        exit_code=1,
    )
    assert list(Path(".").glob("dossier_*.json")) == []


def test_cli_json_reads_pass_utf8():
    import re

    src = Path(main.__file__).read_text(encoding="utf-8")
    bare = [
        ln
        for ln in src.splitlines()
        if re.search(r"\.read_text\(\)", ln) and "_CONFIG_FILE" not in ln
    ]
    assert bare == []
