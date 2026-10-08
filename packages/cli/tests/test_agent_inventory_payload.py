"""The declared agent inventory reaches the Annex IV dossier on both CLI paths (SU-26c)."""

from __future__ import annotations

import json

from opencomplai_cli import main
from opencomplai_cli.agent_inventory_payload import agent_inventory_payload
from opencomplai_cli.publish import prepare_dossier_envelope
from opencomplai_core.models import SystemManifest
from typer.testing import CliRunner

runner = CliRunner()

_BLOCK = {
    "agents": [
        {
            "id": "triage",
            "name": "Triage agent",
            "tools": [{"name": "search", "kind": "function"}],
            "mandate": {"permitted_actions": ["tool:search"]},
        }
    ]
}


def _manifest(**extra) -> dict:
    return {
        "system_id": "inventory-sys",
        "intended_purpose": "chatbot",
        "compliance_target": "EU_AI_ACT",
        "high_risk_presumption": False,
        "commit_ref": "HEAD",
        **extra,
    }


def _expected() -> dict:
    return SystemManifest(
        **_manifest(agent_inventory=_BLOCK)
    ).agent_inventory.model_dump(mode="json")


def test_payload_unchanged_without_inventory():
    assert agent_inventory_payload(SystemManifest(**_manifest())) == {}
    assert agent_inventory_payload(object()) == {}


def test_docs_generate_service_payload_carries_inventory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENCOMPLAI_API_URL", "http://svc.invalid")
    calls: list[tuple[str, dict]] = []

    def fake(path: str, payload: dict) -> tuple[int, dict]:
        calls.append((path, payload))
        return 200, {"dossier_id": "d", "bundle_checksum": "sha256:x"}

    monkeypatch.setattr(main, "_call_service", fake)
    (tmp_path / "m.json").write_text(json.dumps(_manifest(agent_inventory=_BLOCK)))
    result = runner.invoke(
        main.app,
        ["docs", "generate", "--system-id", "inventory-sys", "--manifest", "m.json"],
    )
    assert result.exit_code == 0, result.output
    assert calls[-1][0] == "/v1/docs/generate"
    assert calls[-1][1]["agent_inventory"] == _expected()


def test_scan_service_payload_carries_inventory(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def fake(path: str, payload: dict) -> tuple[int, dict]:
        calls.append((path, dict(payload)))
        if path == "/v1/manifests/validate":
            return 200, {"valid": True}
        if path == "/v1/risk/classify":
            return 200, {
                "risk_class": "minimal",
                "profiling_detected": False,
                "trap_detected": False,
                "rationale_hash": "sha256:" + "a" * 64,
            }
        if path == "/v1/verify/claims":
            return 200, {"outcome": "verified"}
        if path == "/v1/docs/generate":
            return 200, {"bundle_checksum": "sha256:" + "b" * 64}
        return 200, {"event_id": None}

    monkeypatch.setattr(main, "_call_service", fake)
    monkeypatch.setattr(main, "_emit_event", lambda *a, **kw: None)
    manifest = SystemManifest(**_manifest(agent_inventory=_BLOCK))
    main._run_service_check(manifest, "HEAD", "local", "install-1")
    (docs,) = [p for path, p in calls if path == "/v1/docs/generate"]
    assert docs["agent_inventory"] == _expected()


def test_docs_generate_local_path_carries_inventory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    (tmp_path / "m.json").write_text(json.dumps(_manifest(agent_inventory=_BLOCK)))
    out = tmp_path / "out"
    result = runner.invoke(
        main.app,
        [
            "docs",
            "generate",
            "--system-id",
            "inventory-sys",
            "--manifest",
            "m.json",
            "--output-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    (dossier_file,) = out.glob("dossier_*.json")
    assert json.loads(dossier_file.read_text())["agent_inventory"] == _expected()


def test_push_envelope_never_carries_inventory():
    dossier = {
        "system_id": "inventory-sys",
        "commit_ref": "a" * 40,
        "compliance_target": "EU_AI_ACT",
        "bundle_checksum": "sha256:" + "0" * 64,
        "generated_at": "2026-10-01T00:00:00+00:00",
        "signature_status": "unsigned",
        "agent_inventory": _expected(),
    }
    envelope = prepare_dossier_envelope(dossier)
    assert "agent_inventory" not in envelope
    dumped = json.dumps(envelope)
    assert "Triage agent" not in dumped
    assert "tool:search" not in dumped
