"""`scan --ai-intent` uses the deterministic `codebert-onnx` matcher by default.

A base install has no llama-cpp, so the old default (`qwen2.5-coder-1.5b`) made a
bare `--ai-intent` print "AI intent skipped". These tests pin the new default and
the three ways to ask for something else: `--ai-model`, a saved config, and
`--propose` (which ignores the config and is covered in `test_scan_propose.py`).

Every test points `_AI_CONFIG_FILE` at a temp path: this machine may have a real
`~/.opencomplai/ai-config.yaml`, and a test must never read it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import opencomplai_cli.main as cli_main
from opencomplai_cli import leads
from opencomplai_cli.main import app
from opencomplai_core.models import SystemManifest
from typer.testing import CliRunner

runner = CliRunner()

_SCREEN = (
    "from sklearn.ensemble import RandomForestClassifier\n\n\n"
    "def screen(applicants):\n"
    "    ranked = rank_candidates(applicants)\n"
    "    return ranked\n"
)


def _base_install(monkeypatch, tmp_path: Path, config: str | None = None) -> None:
    monkeypatch.setitem(sys.modules, "llama_cpp", None)
    cfg = tmp_path / "ai-config.yaml"
    if config is not None:
        cfg.write_text(config, encoding="utf-8")
    monkeypatch.setattr("opencomplai_ai.config._AI_CONFIG_FILE", cfg)
    # A saved model that needs a download must not look in the real model cache.
    monkeypatch.setattr(
        "opencomplai_ai.downloader.get_cache_dir", lambda: tmp_path / "models"
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "a.py").write_text(_SCREEN, encoding="utf-8")
    return repo


def _scan(tmp_path: Path, *extra: str):
    manifest = tmp_path / "system-manifest.json"
    manifest.write_text(
        SystemManifest(
            system_id="intent-sys", intended_purpose="customer support chatbot"
        ).model_dump_json(),
        encoding="utf-8",
    )
    return runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(_repo(tmp_path)),
            "--no-emit-evidence",
            "--no-ocignore-bootstrap",
            "--ai-intent",
            *extra,
        ],
    )


def test_ai_intent_runs_on_a_base_install_without_a_model_flag(
    monkeypatch, tmp_path: Path
) -> None:
    _base_install(monkeypatch, tmp_path)
    result = _scan(tmp_path, "-o", "json")
    assert result.exit_code == 0, result.output
    assert "AI intent skipped" not in result.stderr
    assert json.loads(result.stdout)["payload"]["eu_ai_scan"] is not None


def test_ai_model_flag_still_passes_the_chosen_model_through(
    monkeypatch, tmp_path: Path
) -> None:
    _base_install(monkeypatch, tmp_path)
    seen: list[str | None] = []

    def preload(model_id):
        seen.append(model_id)
        return False  # the scan then completes without the intent analysis

    monkeypatch.setattr(cli_main, "_preload_ai_model", preload)
    result = _scan(tmp_path, "--ai-model", "qwen2.5-coder-1.5b", "-o", "json")
    assert result.exit_code == 0, result.output
    assert seen == ["qwen2.5-coder-1.5b"]


def test_a_saved_model_still_wins_over_the_default(monkeypatch, tmp_path: Path) -> None:
    _base_install(monkeypatch, tmp_path, "model_id: qwen2.5-coder-0.5b\n")
    result = _scan(tmp_path, "-o", "json")
    assert result.exit_code == 0, result.output
    assert "AI intent skipped" in result.stderr


def test_ai_intent_still_turns_the_leads_side_channel_off(monkeypatch) -> None:
    monkeypatch.delenv("OPENCOMPLAI_LEADS", raising=False)
    assert leads.want_leads(False, False, False) is True  # leads on by default
    assert leads.want_leads(True, False, False) is False


def test_ai_configure_menu_defaults_to_the_deterministic_matcher(
    monkeypatch, tmp_path: Path
) -> None:
    _base_install(monkeypatch, tmp_path)
    asked: dict = {}

    class _Answer:
        def ask(self):
            return None  # the user leaves the menu

    def select(message, choices, default=None, **_kw):
        asked.update(choices=list(choices), default=default)
        return _Answer()

    monkeypatch.setattr("questionary.select", select)
    result = runner.invoke(app, ["ai", "configure"])
    assert result.exit_code == 0, result.output
    assert asked["default"] == "codebert-onnx"
    assert asked["choices"]
    assert not any("recommended" in c.title.lower() for c in asked["choices"])
