"""Structured human oversight reaches Annex IV section 3 on both CLI paths (SU-20a2)."""

from __future__ import annotations

import json

from opencomplai_cli import main
from opencomplai_cli.oversight_payload import oversight_payload
from opencomplai_core.models import SystemManifest
from typer.testing import CliRunner

runner = CliRunner()

_BLOCK = {
    "roles": [
        {
            "role": "Duty officer",
            "authority": "May suspend the system",
            "can_intervene": True,
            "conditions": ["Drift alarm fires"],
            "training_ref": "training/oversight.md",
        }
    ],
    "escalation": "Duty officer, then CTO",
    "evidence_refs": ["docs/oversight.md"],
}


def _manifest(**extra) -> dict:
    return {
        "system_id": "oversight-sys",
        "intended_purpose": "chatbot",
        "compliance_target": "EU_AI_ACT",
        "high_risk_presumption": False,
        "commit_ref": "HEAD",
        **extra,
    }


def test_payload_unchanged_without_oversight():
    assert oversight_payload(SystemManifest(**_manifest())) == {}
    assert oversight_payload(object()) == {}


def test_docs_generate_service_payload_carries_oversight(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENCOMPLAI_API_URL", "http://svc.invalid")
    calls: list[tuple[str, dict]] = []

    def fake(path: str, payload: dict) -> tuple[int, dict]:
        calls.append((path, payload))
        return 200, {"dossier_id": "d", "bundle_checksum": "sha256:x"}

    monkeypatch.setattr(main, "_call_service", fake)
    for extra, expect in (
        (_manifest(human_oversight=_BLOCK), True),
        (_manifest(), False),
    ):
        (tmp_path / "m.json").write_text(json.dumps(extra))
        result = runner.invoke(
            main.app,
            [
                "docs",
                "generate",
                "--system-id",
                "oversight-sys",
                "--manifest",
                "m.json",
            ],
        )
        assert result.exit_code == 0, result.output
        payload = calls[-1][1]
        assert ("human_oversight" in payload) is expect
        if expect:
            assert payload["human_oversight"] == _BLOCK
    assert {p for p, _ in calls} == {"/v1/docs/generate"}


def test_scan_service_payload_carries_oversight(monkeypatch):
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
    for manifest, expect in (
        (SystemManifest(**_manifest(human_oversight=_BLOCK)), True),
        (SystemManifest(**_manifest()), False),
    ):
        calls.clear()
        main._run_service_check(manifest, "HEAD", "local", "install-1")
        docs = [p for path, p in calls if path == "/v1/docs/generate"]
        assert len(docs) == 1
        assert ("human_oversight" in docs[0]) is expect
        if expect:
            assert docs[0]["human_oversight"] == manifest.human_oversight.model_dump(
                mode="json"
            )


def test_docs_generate_local_path_carries_structured_oversight(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    manifest = SystemManifest(**_manifest(human_oversight=_BLOCK))
    (tmp_path / "m.json").write_text(manifest.model_dump_json())
    out = tmp_path / "out"
    result = runner.invoke(
        main.app,
        [
            "docs",
            "generate",
            "--system-id",
            "oversight-sys",
            "--manifest",
            "m.json",
            "--output-dir",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    (dossier_file,) = out.glob("dossier_*.json")
    dossier = json.loads(dossier_file.read_text())
    assert dossier["section3"][
        "human_oversight"
    ] == manifest.human_oversight.model_dump(mode="json")
