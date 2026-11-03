"""`docs generate` adds the ISO/IEC 27090 cybersecurity part only when it is a target."""

from __future__ import annotations

import json
from pathlib import Path

from opencomplai_cli import main
from typer.testing import CliRunner

runner = CliRunner()

ISO = "ISO_IEC_27090"
_SYSTEM_ID = "cyber-sys"


def _manifest(*, targets: bool = True, **extra) -> dict:
    block: dict = {}
    if targets:
        block = {
            "compliance_targets": ["EU_AI_ACT", ISO],
            "framework_inputs": {
                ISO: {
                    "attested": {
                        f"{ISO}:5.5": {
                            "statement": "Third-party models are pinned by hash.",
                            "attested_by": "ciso@example.com",
                            "attested_at": "2026-11-02",
                        }
                    },
                    "excluded": {f"{ISO}:7.9": "Model size is set by the provider."},
                }
            },
        }
    return {
        "system_id": _SYSTEM_ID,
        "intended_purpose": "chatbot",
        "compliance_target": "EU_AI_ACT",
        "high_risk_presumption": False,
        "commit_ref": "HEAD",
        **block,
        **extra,
    }


def _run(tmp_path: Path, monkeypatch, manifest: dict, *extra: str):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    (tmp_path / "m.json").write_text(json.dumps(manifest))
    out = tmp_path / "out"
    result = runner.invoke(
        main.app,
        [
            "docs",
            "generate",
            "--system-id",
            _SYSTEM_ID,
            "--manifest",
            "m.json",
            "--output-dir",
            str(out),
            *extra,
        ],
    )
    return result, out


def _dossier_json(out: Path) -> dict:
    (path,) = out.glob("dossier_*.json")
    return json.loads(path.read_text(encoding="utf-8"))


def test_local_dossier_carries_the_part_when_27090_is_a_target(tmp_path, monkeypatch):
    result, out = _run(tmp_path, monkeypatch, _manifest(), "--render", "md")
    assert result.exit_code == 0, result.output
    part = _dossier_json(out)["cybersecurity"]
    assert part["framework"] == ISO
    assert len(part["entries"]) == 30
    by_id = {e["clause_id"]: e for e in part["entries"]}
    assert by_id[f"{ISO}:5.5"]["status"] == "met"
    assert by_id[f"{ISO}:5.5"]["evidence_ref"] == (
        "attestation:ciso@example.com@2026-11-02"
    )
    assert part["excluded"] == [
        {
            "clause_id": f"{ISO}:7.9",
            "heading": "Optimising the size of the model",
            "reason": "Model size is set by the provider.",
        }
    ]
    (md_path,) = out.glob("dossier_*.md")
    md = md_path.read_text(encoding="utf-8")
    assert "## Cybersecurity measures (Annex IV point 2(h), ISO/IEC 27090)" in md
    assert f"{ISO}:7.9 Optimising the size of the model" in md


def test_local_dossier_has_no_part_without_the_target(tmp_path, monkeypatch):
    result, out = _run(
        tmp_path, monkeypatch, _manifest(targets=False), "--render", "md"
    )
    assert result.exit_code == 0, result.output
    assert "cybersecurity" not in _dossier_json(out)
    (md_path,) = out.glob("dossier_*.md")
    assert "Cybersecurity" not in md_path.read_text(encoding="utf-8")


def test_bad_attestation_id_exits_2(tmp_path, monkeypatch):
    manifest = _manifest()
    manifest["framework_inputs"][ISO]["attested"][f"{ISO}:9.99"] = {
        "statement": "x",
        "attested_by": "a",
        "attested_at": "2026-11-02",
    }
    result, _ = _run(tmp_path, monkeypatch, manifest)
    assert result.exit_code == 2, result.output


def test_service_mode_warns_that_the_part_needs_local_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENCOMPLAI_API_URL", "http://svc.invalid")
    monkeypatch.setattr(
        main, "_call_service", lambda path, payload: (200, {"dossier_id": "d"})
    )
    (tmp_path / "m.json").write_text(json.dumps(_manifest()))
    result = runner.invoke(
        main.app,
        ["docs", "generate", "--system-id", _SYSTEM_ID, "--manifest", "m.json"],
    )
    assert result.exit_code == 0, result.output
    assert "cybersecurity section needs local mode" in " ".join(result.output.split())
