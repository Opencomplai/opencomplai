"""Docs claims that the closeout round fixed must stay true (CL-F15).

Each guard names the claim it protects; deleting the claim from its page fails the test.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import typer.main
from opencomplai_cli.main import app
from opencomplai_core.frameworks import FRAMEWORKS

ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "src"
AGENT_LOG = ROOT / "packages" / "sdk-python" / "src" / "opencomplai" / "agent_log.py"
BASELINE = ROOT / "tools" / "mypy-gate" / "baseline.json"
_ISO_MAPPED_ONLY = re.compile(
    r"42001[^.;\n]{0,40}\b(?:is|are) (?:mapped,? not evaluated|mapped only)"
    r"|no verdict is computed for (?:it|ISO)",
    re.IGNORECASE,
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(page: str, heading: str, until: str) -> str:
    start = page.index(heading)
    return page[start : page.index(until, start)]


def _public_methods(path: Path, class_name: str) -> list[str]:
    tree = ast.parse(_text(path))
    cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name
    )
    return [
        n.name
        for n in cls.body
        if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
    ]


def test_sdk_reference_documents_agent_decision_log():
    section = _section(
        _text(DOCS / "sdk" / "api-reference.md"), "## `AgentDecisionLog`", "## Enums"
    )
    assert "AgentDecisionLog" in section
    methods = _public_methods(AGENT_LOG, "AgentDecisionLog")
    assert {"record", "entries", "head", "verify"} <= set(methods)
    for method in methods:
        assert re.search(rf"`{method}\(", section), method
    assert "expected_head" in section
    assert "expected_count" in section
    assert "verify-log" in section


def test_supply_chain_page_documents_the_trivy_record():
    page = _text(DOCS / "security" / "supply-chain.md")
    before_python = page[: page.index("## Python packages")]
    assert "infra/docker/TRIVY-LAST-RUN.md" in before_python
    assert (
        "https://github.com/Opencomplai/opencomplai/blob/main/infra/docker/TRIVY-LAST-RUN.md"
        in before_python
    )
    assert "test_docker_images_hardening.py" in before_python


def test_testing_page_says_wheel_smoke_needs_network():
    text = _text(DOCS / "contributing" / "testing.md")
    assert "It needs `uv` and network access" in text


def test_development_setup_documents_the_mypy_gate():
    pin = json.loads(_text(BASELINE))["mypy_version"]
    text = _text(DOCS / "contributing" / "development-setup.md")
    assert (
        f"uv run --with mypy=={pin} python tools/mypy-gate/mypy_gate.py --check" in text
    )
    assert "uv run mypy packages/" not in text
    assert "tools/mypy-gate/baseline.json" in text


def test_gaps_target_help_and_page_name_every_framework():
    page = _text(DOCS / "cli" / "gaps.md")
    row = next(ln for ln in page.splitlines() if ln.startswith("| `--target`"))
    gaps = typer.main.get_command(app).commands["gaps"]
    target = next(p for p in gaps.params if "--target" in p.opts)
    for key in FRAMEWORKS:
        assert key in row, key
        assert key in (target.help or ""), key


def test_no_docs_page_calls_iso_42001_mapped_only():
    hits = [
        path.relative_to(ROOT).as_posix()
        for path in sorted(DOCS.rglob("*.md"))
        if _ISO_MAPPED_ONLY.search(_text(path))
    ]
    assert not hits, hits
