"""Golden snapshots of today's EU AI Act (and NIST AI RMF) CLI output.

Pins what `init`, `gaps`, `check --with-gaps`, `recommend` and `report`
produce for a small temp repo, so later changes can prove that EU-only and
NIST-only runs stay byte-identical. Volatile values (timestamps, versions,
install ids, durations, commit hashes, temp paths) are normalised first.

Snapshots live in golden/. Regenerate them only on purpose:
    OPENCOMPLAI_UPDATE_GOLDEN=1 uv run pytest packages/cli/tests/test_golden_eu_output.py
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
from pathlib import Path

import pytest
from opencomplai_cli import main
from rich.console import Console
from typer.testing import CliRunner

GOLDEN = Path(__file__).parent / "golden"
UPDATE = os.environ.get("OPENCOMPLAI_UPDATE_GOLDEN") == "1"

CREDIT = "credit scoring for loan applications"
CHATBOT = "customer support chatbot for an online shop"

# Both content-marker groups the risk_register probe looks for, so Art. 9
# reads as content-bearing evidence rather than a bare file.
RISK_REGISTER = """# Risk register

## Risk identification
Identified risks: biased scoring of thin-file applicants.

## Mitigation
Control measure: quarterly bias review; residual risk accepted by the CRO.
"""

_VOLATILE = (
    (
        re.compile(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
        ),
        "<TIMESTAMP>",
    ),
    (re.compile(r'("tool_version":\s*")[^"]*"'), r'\1<VERSION>"'),
    (re.compile(r'("install_id":\s*")[^"]*"'), r'\1<INSTALL_ID>"'),
    (re.compile(r'("duration_ms":\s*)\d+'), r"\1<DURATION>"),
    (re.compile(r"\b[0-9a-f]{40}\b"), "<COMMIT>"),
)


def _normalise(text: str, tmp_path: Path) -> str:
    for base in (tmp_path.resolve(), tmp_path):
        for form in (str(base), base.as_posix(), json.dumps(str(base))[1:-1]):
            text = text.replace(form, "<TMP>")
    for pattern, repl in _VOLATILE:
        text = pattern.sub(repl, text)
    # LF only, no trailing blanks, one final newline: stable across OSes
    # and untouched by whitespace-fixing hooks.
    return "\n".join(line.rstrip() for line in text.splitlines()) + "\n"


def _assert_golden(name: str, text: str) -> None:
    path = GOLDEN / name
    if UPDATE:
        path.parent.mkdir(exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return
    assert path.is_file(), f"missing {path}; run with OPENCOMPLAI_UPDATE_GOLDEN=1"
    assert text == path.read_text(encoding="utf-8"), f"{name} drifted"


@pytest.fixture
def cli(tmp_path, monkeypatch):
    """Run the CLI inside a temp repo with mixed evidence; returns stdout."""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "risk_register.md").write_text(RISK_REGISTER, encoding="utf-8")
    (repo / "INSTRUCTIONS.md").write_text(
        "# Instructions for use\n\nReview every decision.\n", encoding="utf-8"
    )
    (repo / "docs" / "qms.md").write_text("", encoding="utf-8")
    monkeypatch.chdir(repo)

    for var in (
        "OPENCOMPLAI_API_URL",
        "OPENCOMPLAI_VAULT_URL",
        "OPENCOMPLAI_RISK_ENGINE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
    home = tmp_path / "home"
    monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home)
    monkeypatch.setattr(main, "_CONFIG_FILE", home / "config.yaml")
    monkeypatch.setattr(main, "_SIGNING_KEY", home / "signing.key")
    monkeypatch.setattr(main, "_SIGNING_PUB", home / "signing.pub")

    out = io.StringIO()

    def console(file: io.StringIO) -> Console:
        return Console(file=file, width=200, color_system=None, legacy_windows=False)

    monkeypatch.setattr(main, "console", console(out))
    monkeypatch.setattr(main, "err_console", console(io.StringIO()))

    def run(*args: str, exit_code: int = 0) -> str:
        out.seek(0)
        out.truncate()
        result = CliRunner().invoke(main.app, list(args))
        assert result.exit_code == exit_code, (result.output, out.getvalue())
        return _normalise(out.getvalue(), tmp_path)

    return run


def _init(cli, purpose: str, target: str = "EU_AI_ACT") -> None:
    cli(
        "init",
        "--system-id",
        "golden-sys",
        "--intended-purpose",
        purpose,
        "--compliance-target",
        target,
    )


def _read(path: str, tmp_path: Path, encoding: str | None = None) -> str:
    # The manifest and artifact are written with the locale encoding (cp1252
    # on Windows), so read them back the same way; report.html is UTF-8.
    return _normalise(Path(path).read_text(encoding=encoding), tmp_path)


def test_init_manifest(cli, tmp_path):
    _init(cli, CREDIT)
    _assert_golden("init_manifest.json", _read("system-manifest.json", tmp_path))


@pytest.mark.parametrize(
    ("name", "purpose", "extra"),
    [
        ("gaps_credit", CREDIT, []),
        ("gaps_chatbot", CHATBOT, []),
        ("gaps_credit_nist", CREDIT, ["--target", "NIST_AI_RMF"]),
    ],
)
def test_gaps(cli, name, purpose, extra):
    _init(cli, purpose)
    _assert_golden(f"{name}.txt", cli("gaps", *extra))
    _assert_golden(f"{name}.json", cli("gaps", *extra, "--output", "json"))


@pytest.mark.parametrize(
    ("name", "purpose", "target", "exit_code"),
    [
        ("check_eu", CREDIT, "EU_AI_ACT", 1),
        ("check_nist", CHATBOT, "NIST_AI_RMF", 0),
    ],
)
def test_check_with_gaps(cli, tmp_path, name, purpose, target, exit_code):
    _init(cli, purpose, target)
    stdout = cli("check", "--with-gaps", "--output", "json", exit_code=exit_code)
    _assert_golden(f"{name}_stdout.json", stdout)
    _assert_golden(f"{name}_artifact.json", _read("compliance-artifact.json", tmp_path))


def test_recommend_files(cli):
    _init(cli, CREDIT)
    cli("recommend", "--output", "fixes")
    lines = []
    for path in sorted(Path("fixes").iterdir()):
        # write_text emits CRLF on Windows; hash the LF form.
        data = path.read_bytes().replace(b"\r\n", b"\n")
        lines.append(f"{path.name}  {hashlib.sha256(data).hexdigest()}")
    _assert_golden("recommend_files.txt", "\n".join(lines) + "\n")


def test_report_html(cli, tmp_path):
    _init(cli, CREDIT)
    cli("check", "--with-gaps", exit_code=1)
    cli("report", "--output", "report.html")
    _assert_golden("report.html", _read("report.html", tmp_path, "utf-8"))


def _assert_matches_golden(name: str, text: str) -> None:
    # Read-only: never rewrites the snapshot, even with OPENCOMPLAI_UPDATE_GOLDEN.
    assert text == (GOLDEN / name).read_text(encoding="utf-8"), f"{name} drifted"


def test_check_with_ungated_project_config(cli, tmp_path):
    # A gate section that lists no frameworks gates nothing.
    Path("opencomplai.yaml").write_text("gate:\n  fail_on: partial\n", encoding="utf-8")
    _init(cli, CHATBOT, "NIST_AI_RMF")
    stdout = cli("check", "--with-gaps", "--output", "json")
    _assert_matches_golden("check_nist_stdout.json", stdout)
    _assert_matches_golden(
        "check_nist_artifact.json", _read("compliance-artifact.json", tmp_path)
    )


def test_gaps_with_ungated_project_config(cli):
    Path("opencomplai.yaml").write_text("gate:\n  frameworks: []\n", encoding="utf-8")
    _init(cli, CREDIT)
    _assert_matches_golden(
        "gaps_credit_nist.txt", cli("gaps", "--target", "NIST_AI_RMF")
    )
