"""Scanner coverage for MCP configs and agent frameworks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from opencomplai_core.models import SignalCategory
from opencomplai_core.scanner.features import extract_features
from opencomplai_core.scanner.inventory import build_repo_inventory
from opencomplai_core.scanner.registry import DETECTOR_REGISTRY


def _features(root: Path):
    return extract_features(build_repo_inventory(root))


def _run(det_id: str, features):
    det = next(d for d in DETECTOR_REGISTRY if d.detector_id == det_id)
    return det.detect(features)


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_mcp_json_inventory_names(tmp_path: Path):
    _write(
        tmp_path,
        ".mcp.json",
        json.dumps(
            {
                "mcpServers": {
                    "files": {"command": "npx", "args": ["--token", "SECRETARG"]},
                    "remote": {"url": "https://x.example/SECRETURL"},
                }
            }
        ),
    )
    _write(tmp_path, "tools/mcp.json", json.dumps({"mcpServers": {"db": {}}}))
    refs = _features(tmp_path).mcp_servers
    assert [(r.name, r.transport) for r in refs] == [
        ("db", "unknown"),
        ("files", "stdio"),
        ("remote", "remote"),
    ]
    assert {r.location for r in refs} == {
        ".mcp.json:mcpServers.files",
        ".mcp.json:mcpServers.remote",
        "tools/mcp.json:mcpServers.db",
    }
    text = repr(refs)
    for secret in ("SECRETARG", "SECRETURL", "npx"):
        assert secret not in text


@pytest.mark.parametrize("body", ["{not json", "[1, 2]", '{"mcpServers": []}'])
def test_mcp_json_malformed_is_ignored(tmp_path: Path, body: str):
    _write(tmp_path, ".mcp.json", body)
    assert _features(tmp_path).mcp_servers == []


def test_agents_detector_emits_mcp_server_evidence(tmp_path: Path):
    _write(tmp_path, ".mcp.json", json.dumps({"mcpServers": {"files": {}}}))
    ev = [
        e
        for e in _run("DET_AGENTS_MCP_V1", _features(tmp_path))
        if e.token_label == "mcp_server:files"
    ]
    assert len(ev) == 1
    assert ev[0].category == SignalCategory.MCP_SERVER
    assert ev[0].rationale_code == "mcp_config_file"


@pytest.mark.parametrize(
    ("pkg", "category"),
    [
        ("litellm", SignalCategory.AI_SDK),
        ("azure-ai-inference", SignalCategory.AI_SDK),
        ("langgraph", SignalCategory.AGENT_FRAMEWORK),
        ("openai-agents", SignalCategory.AGENT_FRAMEWORK),
        ("pydantic-ai", SignalCategory.AGENT_FRAMEWORK),
        ("smolagents", SignalCategory.AGENT_FRAMEWORK),
        ("google-adk", SignalCategory.AGENT_FRAMEWORK),
        ("@mastra/core", SignalCategory.AGENT_FRAMEWORK),
    ],
)
def test_listed_packages_detected(tmp_path: Path, pkg: str, category):
    if pkg.startswith("@"):
        _write(
            tmp_path,
            "package.json",
            json.dumps({"dependencies": {pkg: "1.0.0"}}),
        )
    else:
        _write(tmp_path, "requirements.txt", f"{pkg}==1.0.0\n")
    cats = {e.category for e in _run("DET_AI_DEP_V1", _features(tmp_path))}
    assert category in cats


def test_package_in_two_lists_reports_both_categories(tmp_path: Path):
    _write(tmp_path, "requirements.txt", "crewai==1.0.0\n")
    ev = _run("DET_AI_DEP_V1", _features(tmp_path))
    assert {e.category for e in ev} == {
        SignalCategory.LLM_ORCHESTRATION,
        SignalCategory.AGENT_FRAMEWORK,
    }
    assert len({e.evidence_id for e in ev}) == len(ev) == 2


def test_import_in_two_lists_reports_both_categories(tmp_path: Path):
    _write(tmp_path, "src/app.py", "import crewai\n")
    ev = _run("DET_AST_V1", _features(tmp_path))
    assert {e.category for e in ev} == {
        SignalCategory.LLM_ORCHESTRATION,
        SignalCategory.AGENT_FRAMEWORK,
    }
    assert len({e.evidence_id for e in ev}) == len(ev) == 2


def test_azure_ai_openai_token_removed():
    from opencomplai_core.scanner.detectors._signals import load_signals

    assert "azure-ai-openai" not in load_signals()["ai_sdks"]


def test_mastra_ts_import_detected(tmp_path: Path):
    _write(
        tmp_path,
        "src/agent.ts",
        'import { Mastra } from "@mastra/core";\nexport const m = new Mastra({});\n',
    )
    ev = _run("DET_AST_V1", _features(tmp_path))
    assert any(e.category == SignalCategory.AGENT_FRAMEWORK for e in ev)
