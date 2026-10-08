"""`opencomplai eval` without --sample-set runs the bundled seed corpus (SU-27b)."""

import json
import socket
from pathlib import Path

import pytest
from opencomplai_cli.main import app
from opencomplai_core.evaluators.seed_corpus import load_seed_corpus
from opencomplai_core.model_providers import ProviderCompletion
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture(autouse=True)
def _local_only(monkeypatch):
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "seed-sys",
            "--intended-purpose",
            "customer support chatbot",
            "--output",
            str(path),
        ],
    )
    assert result.exit_code == 0, result.output
    return path


def test_eval_without_sample_set_runs_offline(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path)

    def _no_network(*args, **kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", _no_network)
    result = runner.invoke(app, ["eval", "--manifest", str(manifest)])
    assert result.exit_code == 0, result.output
    assert "bundled seed corpus" in result.output
    assert "EVAL_ADVERSARIAL_V1" in result.output
    assert "skipped" in result.output.lower()


def test_eval_explicit_sample_set_unchanged(tmp_path):
    manifest = _manifest(tmp_path)
    sample = tmp_path / "set.json"
    sample.write_text(
        json.dumps({"eval_set_id": "s1", "system_id": "seed-sys", "outputs": ["hi"]}),
        encoding="utf-8",
    )
    result = runner.invoke(
        app, ["eval", "--manifest", str(manifest), "--sample-set", str(sample)]
    )
    assert result.exit_code == 0, result.output
    assert "seed corpus" not in result.output


def test_eval_seed_with_provider_scores_outputs(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path)
    calls: list[str] = []

    class _Client:
        def complete(self, prompt, *, model, api_key):
            calls.append(prompt)
            return ProviderCompletion("fake", model, prompt, "I cannot help with that.")

    def fake(provider, **kwargs):
        return _Client()

    monkeypatch.setattr("opencomplai_core.model_providers.get_provider_client", fake)
    monkeypatch.setenv("OPENCOMPLAI_PROVIDER_API_KEY", "dummy")
    result = runner.invoke(
        app,
        [
            "eval",
            "--manifest",
            str(manifest),
            "--provider",
            "fake",
            "--model",
            "m",
        ],
    )
    assert result.exit_code == 0, result.output
    # one call per seed prompt (not repeated for the printed payload)
    assert len(calls) == len(load_seed_corpus()["prompts"])
    assert "Live provider call" in result.output
    # the live refusals were scored: adversarial is no longer in the skipped list
    assert "overall: pass" in result.output
    assert "EVAL_ADVERSARIAL_V1" not in result.output
    assert "no_prompt_output_pairs" not in result.output


def test_eval_still_requires_manifest(tmp_path):
    result = runner.invoke(app, ["eval", "--manifest", str(tmp_path / "missing.json")])
    assert result.exit_code == 2
