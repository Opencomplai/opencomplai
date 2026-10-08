"""`opencomplai init --from-model-card`: offline import, attested not verified."""

import json
from pathlib import Path

from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()

_CARD = """---
license: apache-2.0
library_name: transformers
pipeline_tag: text-classification
base_model: distilbert-base-uncased
datasets:
  - imdb
  - sst2
tags: [sentiment]
model-index:
  - name: demo
    results:
      - dataset: {type: imdb, name: IMDB}
        metrics:
          - {type: accuracy, value: 0.93}
          - {type: f1, value: 0.92}
---

# demo
"""


def _init(tmp_path: Path, purpose: str, *extra: str, card: str | None = _CARD):
    out = tmp_path / "system-manifest.json"
    args = [
        "init",
        "--system-id",
        "s1",
        "--intended-purpose",
        purpose,
        "--output",
        str(out),
    ]
    if card is not None:
        card_file = tmp_path / "README.md"
        card_file.write_text(card, encoding="utf-8")
        args += ["--from-model-card", str(card_file)]
    return runner.invoke(app, [*args, *extra]), out


def test_init_from_card_fills_mapped_fields(tmp_path):
    result, out = _init(tmp_path, "customer support chatbot")
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert "imdb, sst2" in data["training_data_description"]
    assert "base_model=distilbert-base-uncased" in data["model_architecture"]
    assert data["performance_metrics"] == {"imdb/accuracy": 0.93, "imdb/f1": 0.92}


def test_init_from_card_records_attested_evidence(tmp_path):
    result, out = _init(tmp_path, "customer support chatbot")
    assert result.exit_code == 0, result.output
    evidence = json.loads(out.read_text())["imported_evidence"]
    assert set(evidence) == {
        "training_data_description",
        "model_architecture",
        "performance_metrics",
    }
    for item in evidence.values():
        assert item["status"] == "attested"
        assert item["source_file"] == "README.md"
        assert str(tmp_path) not in json.dumps(item)


def test_explicit_flags_win_over_card(tmp_path):
    result, out = _init(
        tmp_path, "customer support chatbot", "--model-architecture", "x"
    )
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text())
    assert data["model_architecture"] == "x"
    assert "model_architecture" not in data["imported_evidence"]
    assert "training_data_description" in data["imported_evidence"]


def _check(workdir: Path, manifest: Path, monkeypatch):
    monkeypatch.chdir(workdir)  # check may write artifacts into the cwd
    result = runner.invoke(
        app, ["check", "--manifest", str(manifest), "--output", "json"]
    )
    return result.exit_code, json.loads(result.stdout)["result"]


def test_check_exit_code_unchanged_by_import(tmp_path, monkeypatch):
    for purpose, code in (
        ("customer support chatbot", 0),
        ("employment screening and ranking", 1),
    ):
        with_dir = tmp_path / f"with{code}"
        without_dir = tmp_path / f"without{code}"
        with_dir.mkdir()
        without_dir.mkdir()
        r1, m1 = _init(with_dir, purpose)
        r2, m2 = _init(without_dir, purpose, card=None)
        assert r1.exit_code == r2.exit_code == 0
        code1, res1 = _check(with_dir, m1, monkeypatch)
        code2, res2 = _check(without_dir, m2, monkeypatch)
        assert code1 == code2 == code
        assert res1 == res2


def test_bad_card_exits_2_without_writing_manifest(tmp_path):
    result, out = _init(
        tmp_path, "customer support chatbot", card="# no front matter\n"
    )
    assert result.exit_code == 2
    assert not out.exists()


def test_deeply_nested_card_exits_2_without_writing_manifest(tmp_path):
    card = "---\ndatasets: " + "[" * 5000 + "]" * 5000 + "\n---\n"
    result, out = _init(tmp_path, "customer support chatbot", card=card)
    assert result.exit_code == 2
    assert not out.exists()


def test_missing_card_file_exits_2(tmp_path):
    out = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            "s1",
            "--intended-purpose",
            "chatbot",
            "--output",
            str(out),
            "--from-model-card",
            str(tmp_path / "nope.md"),
        ],
    )
    assert result.exit_code == 2
    assert not out.exists()


def test_from_model_card_with_interactive_exits_2(tmp_path):
    card = tmp_path / "README.md"
    card.write_text(_CARD, encoding="utf-8")
    result = runner.invoke(
        app, ["init", "--interactive", "--from-model-card", str(card)]
    )
    assert result.exit_code == 2


def test_validate_manifest_accepts_imported_manifest(tmp_path):
    result, out = _init(tmp_path, "customer support chatbot")
    assert result.exit_code == 0, result.output
    assert runner.invoke(app, ["validate-manifest", str(out)]).exit_code == 0


def test_import_then_check_non_cp1252_card(tmp_path, monkeypatch):
    # Emulate a cp1252 locale: reads without an explicit encoding decode as cp1252.
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    orig = Path.read_text

    def legacy_read_text(self, encoding=None, errors=None):
        if encoding is None:
            return self.read_bytes().decode("cp1252")
        return orig(self, encoding, errors)

    monkeypatch.setattr(Path, "read_text", legacy_read_text)
    card = _CARD.replace("  - sst2", "  - Łódź 中文")
    result, out = _init(tmp_path, "customer support chatbot", card=card)
    assert result.exit_code == 0, result.output
    assert "Łódź 中文" in out.read_text(encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    checked = runner.invoke(app, ["check", "--manifest", str(out), "--output", "json"])
    assert checked.exit_code == 0, checked.output
    assert "Manifest validation error" not in checked.output
