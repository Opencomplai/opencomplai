"""`--sort priority` on gaps, report and recommend (presentation-only order).

The `cli` fixture and `_init` are copied from test_golden_eu_output.py on
purpose: test modules do not import each other. Deadlines are injected by
patching `opencomplai_core.backlog.deadline_for`, so no clock is involved.
"""

from __future__ import annotations

import io
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_core import backlog
from rich.console import Console
from typer.testing import CliRunner

CREDIT = "credit scoring for loan applications"

RISK_REGISTER = """# Risk register

## Risk identification
Identified risks: biased scoring of thin-file applicants.

## Mitigation
Control measure: quarterly bias review; residual risk accepted by the CRO.
"""


def _normalise(text: str, tmp_path: Path) -> str:
    for base in (tmp_path.resolve(), tmp_path):
        for form in (str(base), base.as_posix(), json.dumps(str(base))[1:-1]):
            text = text.replace(form, "<TMP>")
    return "\n".join(line.rstrip() for line in text.splitlines()) + "\n"


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
        "GITHUB_SHA",
        "CI_COMMIT_SHA",
    ):
        monkeypatch.delenv(var, raising=False)
    # the goldens pin commit_ref "unresolved": never resolve an enclosing repo
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
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


def _articles(cli) -> list[dict]:
    return json.loads(cli("gaps", "--output", "json"))["payload"]["articles"]


def _reverse_deadlines(monkeypatch, articles: list[dict]) -> list[str]:
    """Give actionable rows deadlines in reverse article order; return the
    expected priority order (reversed actionable rows, then MET rows)."""
    todo = [a["article"] for a in articles if a["status"] != "met"]
    met = [a["article"] for a in articles if a["status"] == "met"]
    start = date(2026, 1, 1)
    dates = {art: start + timedelta(days=i) for i, art in enumerate(reversed(todo))}
    monkeypatch.setattr(backlog, "deadline_for", dates.get)
    return [*reversed(todo), *met]


def test_gaps_human_priority_order(cli, monkeypatch):
    _init(cli, CREDIT)
    articles = _articles(cli)
    expected = _reverse_deadlines(monkeypatch, articles)
    assert expected != [a["article"] for a in articles]
    out = cli("gaps", "--sort", "priority")
    assert re.findall(r"^│ (Art\. \d+)\s", out, re.M) == expected
    assert "Ordered by deadline, severity, effort." in out


def test_gaps_json_backlog_block_ordered(cli, monkeypatch):
    _init(cli, CREDIT)
    articles = _articles(cli)
    expected = _reverse_deadlines(monkeypatch, articles)
    text = cli("gaps", "--sort", "priority", "--output", "json")
    payload = json.loads(text)["payload"]
    block = payload["backlog"]
    met = {a["article"] for a in articles if a["status"] == "met"}
    assert [b["article"] for b in block] == [e for e in expected if e not in met]
    assert [b["rank"] for b in block] == list(range(1, len(block) + 1))
    assert all(
        set(b) == {"rank", "article", "status", "deadline", "effort"} for b in block
    )
    assert block[0]["deadline"] == "2026-01-01"
    # the data itself stays in article order
    assert [a["article"] for a in payload["articles"]] == [
        a["article"] for a in articles
    ]
    assert not re.search(r"days?", text)


def test_report_html_priority_order(cli, monkeypatch, tmp_path):
    _init(cli, CREDIT)
    articles = _articles(cli)
    expected = _reverse_deadlines(monkeypatch, articles)
    cli("check", "--with-gaps", exit_code=1)
    cli("report", "--sort", "priority", "--output", "report.html")
    html = Path("report.html").read_text(encoding="utf-8")
    start = html.index('id="gap-table"')
    table = html[start : html.index("</table>", start)]
    assert re.findall(r"<tr><td>(Art\. \d+)</td>", table) == expected


def test_recommend_priority_order(cli, monkeypatch):
    _init(cli, CREDIT)
    articles = _articles(cli)
    expected = _reverse_deadlines(monkeypatch, articles)
    default = cli("recommend", "--output", "fx-default")
    out = cli("recommend", "--output", "fx-priority", "--sort", "priority")

    def order(text: str) -> list[str]:
        names = re.findall(r"fx-[a-z]+[\\/](art\d+)-", text)
        return list(dict.fromkeys(names))

    # only EU rows with a template are written; all must follow priority order
    rank = {f"art{a.split()[1]}": i for i, a in enumerate(expected)}
    got = order(out)
    assert got == sorted(got, key=rank.__getitem__)
    assert got != order(default)
    assert sorted(got) == sorted(order(default))


def test_default_sort_is_article_and_has_no_backlog_block(cli):
    _init(cli, CREDIT)
    default = json.loads(cli("gaps", "--output", "json"))["payload"]
    assert "backlog" not in default
    explicit = json.loads(cli("gaps", "--sort", "article", "--output", "json"))
    assert {**explicit["payload"], "generated_at": 0} == {**default, "generated_at": 0}
    assert "Ordered by deadline" not in cli("gaps")


def test_invalid_sort_exits_2(cli):
    _init(cli, CREDIT)
    for command in ("gaps", "recommend", "report"):
        cli(command, "--sort", "bogus", exit_code=2)


def test_priority_json_still_feeds_recommend_and_report(cli, monkeypatch):
    _init(cli, CREDIT)
    _reverse_deadlines(monkeypatch, _articles(cli))
    Path("gaps.json").write_text(
        cli("gaps", "--sort", "priority", "--output", "json"), encoding="utf-8"
    )
    cli("recommend", "--gap-report", "gaps.json", "--output", "fx-a")
    cli("recommend", "--output", "fx-b")
    assert sorted(p.name for p in Path("fx-a").iterdir()) == sorted(
        p.name for p in Path("fx-b").iterdir()
    )
    cli("check", "--with-gaps", exit_code=1)
    cli("report", "--gap-report", "gaps.json", "--output", "report.html")
    assert Path("report.html").is_file()
