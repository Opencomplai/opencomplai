"""The `opencomplai serve` page must stay in step with the command."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import typer.main
from opencomplai_cli.main import app
from typer.testing import CliRunner

PAGE = Path(__file__).resolve().parents[3] / "docs" / "src" / "cli" / "serve.md"
SERVE_SRC = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "opencomplai_cli"
    / "commands"
    / "serve.py"
)

pytestmark = pytest.mark.skipif(not PAGE.is_file(), reason="docs page absent")


def _params() -> dict:
    return {p.name: p for p in typer.main.get_command(app).commands["serve"].params}


def test_serve_page_lists_every_option_with_its_default() -> None:
    text = PAGE.read_text(encoding="utf-8")
    params = _params()
    assert set(params) == {"project_root", "host", "port"}
    assert "`PROJECT_ROOT`" in text
    assert f"| `{params['project_root'].default}` |" in text
    for name in ("host", "port"):
        row = re.search(rf"^\| `--{name}` \| `([^`]*)` \|", text, re.M)
        assert row, f"--{name} row missing"
        assert row.group(1) == str(params[name].default)


def test_non_loopback_host_exits_two_and_page_says_so() -> None:
    result = CliRunner().invoke(app, ["serve", ".", "--host", "0.0.0.0"])
    assert result.exit_code == 2
    assert re.search(r"rejected \(exit `2`\)", PAGE.read_text(encoding="utf-8"))


def test_install_hint_on_page_matches_the_command_message() -> None:
    src = SERVE_SRC.read_text(encoding="utf-8")
    hint = re.search(r"pip install '([^']+)'", src)
    assert hint
    assert f"pip install '{hint.group(1)}'" in PAGE.read_text(encoding="utf-8")


def test_page_has_no_duplicate_code_fences_and_no_internal_names() -> None:
    text = PAGE.read_text(encoding="utf-8")
    blocks = re.findall(r"```\w*\n(.*?)```", text, re.S)
    assert len(blocks) == len(set(blocks))
    assert text.count("opencomplai serve [PROJECT_ROOT] [OPTIONS]") == 1
    assert "run_serve" not in text
