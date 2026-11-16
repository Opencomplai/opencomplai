"""CLI tests for `opencomplai scaffold`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_cli.main import app
from opencomplai_core import pack_registry
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture
def packs(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "packs"
    scaffolds = root / "DEMO" / "scaffolds"
    scaffolds.mkdir(parents=True)
    (scaffolds / "policy.md").write_text(
        "# Policy\n\n<!-- clause: 5.2 -->\n_fill in_\n", encoding="utf-8"
    )
    (scaffolds / "scaffolds.json").write_text(
        json.dumps(
            {
                "policy": {
                    "title": "Policy",
                    "target": "docs/demo/policy.md",
                    "probe": "demo_policy",
                    "file": "policy.md",
                },
                "register": {
                    "title": "Register",
                    "target": "docs/demo/register.md",
                    "probe": "demo_register",
                    "file": "policy.md",
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "BARE").mkdir()
    monkeypatch.setattr(pack_registry, "PACKS_DIR", root)
    return root


def _run(*args: str):
    return runner.invoke(app, ["scaffold", *args])


def test_list_prints_documents_and_writes_nothing(packs, tmp_path):
    out = tmp_path / "out"
    result = _run("DEMO", "--list", "--output-dir", str(out))
    assert result.exit_code == 0, result.output
    assert "policy" in result.output
    assert "docs/demo/register.md" in result.output
    assert not out.exists()


def test_write_all(packs, tmp_path):
    out = tmp_path / "out"
    result = _run("DEMO", "--output-dir", str(out), "--output", "json")
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["framework"] == "DEMO"
    assert len(payload["created"]) == 2
    assert payload["skipped"] == []
    text = (out / "docs" / "demo" / "policy.md").read_text(encoding="utf-8")
    assert "_fill in_" in text
    assert "<!-- clause: 5.2 -->" in text


def test_write_one(packs, tmp_path):
    out = tmp_path / "out"
    result = _run("DEMO", "register", "--output-dir", str(out))
    assert result.exit_code == 0, result.output
    assert (out / "docs" / "demo" / "register.md").is_file()
    assert not (out / "docs" / "demo" / "policy.md").exists()


def test_existing_file_skipped_without_force(packs, tmp_path):
    out = tmp_path / "out"
    target = out / "docs" / "demo" / "policy.md"
    target.parent.mkdir(parents=True)
    target.write_text("mine", encoding="utf-8")

    result = _run("DEMO", "policy", "--output-dir", str(out), "--output", "json")
    payload = json.loads(result.output)
    assert payload["created"] == []
    assert len(payload["skipped"]) == 1
    assert target.read_text(encoding="utf-8") == "mine"

    result = _run("DEMO", "policy", "--output-dir", str(out), "--force")
    assert result.exit_code == 0, result.output
    assert "_fill in_" in target.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "args",
    [
        ("NOPE",),
        ("DEMO", "missing-doc"),
        ("BARE",),
        ("GDPR",),
    ],
)
def test_exit_2_cases(packs, tmp_path, args):
    out = tmp_path / "out"
    result = _run(*args, "--output-dir", str(out))
    assert result.exit_code == 2, result.output
    assert not out.exists()
