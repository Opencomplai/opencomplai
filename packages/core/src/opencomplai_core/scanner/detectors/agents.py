"""MCP / agent-pattern detector — pattern signals only (not a compliance verdict)."""

from __future__ import annotations

import re

from opencomplai_core.models import (
    EvidenceItem,
    EvidenceKind,
    Reachability,
    SignalCategory,
)
from opencomplai_core.scanner.base import BaseDetector
from opencomplai_core.scanner.detectors._common import build_evidence
from opencomplai_core.scanner.feature_types import FeatureStore

_MCP_IMPORT = re.compile(r"\b(?:mcp|modelcontextprotocol)\b", re.I)
_TOOL_DEF = re.compile(
    r"\b(?:@server\.tool|FastMCP|mcp\.tool|tool_calls?|function_call)\b",
    re.I,
)
_MULTI_AGENT = re.compile(
    r"\b(?:CrewAI|Autogen|AutoGen|multi[_-]?agent|AgentExecutor)\b",
)


class AgentsDetector(BaseDetector):
    """Detect MCP servers, tool definitions, and multi-agent orchestration signals."""

    @property
    def detector_id(self) -> str:
        return "DET_AGENTS_MCP_V1"

    @property
    def detector_version(self) -> str:
        return "1.0.0"

    @property
    def supported_languages(self) -> frozenset[str]:
        return frozenset({"python", "javascript", "typescript", "json", "yaml", "markdown"})

    @property
    def evidence_kinds(self) -> frozenset[str]:
        return frozenset({"prompt_template", "dependency"})

    def detect(self, features: FeatureStore) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []

        for imp in features.imports:
            if _MCP_IMPORT.search(imp.module) or _MCP_IMPORT.search(imp.location):
                evidence.append(
                    build_evidence(
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        evidence_kind=EvidenceKind.DEPENDENCY,
                        category=SignalCategory.MCP_SERVER,
                        token_label="mcp",
                        location=imp.location,
                        scope=imp.scope,
                        rationale_code="mcp_import",
                        confidence=0.75,
                        reachability=Reachability.IMPORT_ONLY,
                    )
                )

        for call in features.callsites:
            blob = f"{call.name} {call.location}"
            if _TOOL_DEF.search(blob) or _MCP_IMPORT.search(blob):
                evidence.append(
                    build_evidence(
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        evidence_kind=EvidenceKind.PROMPT_TEMPLATE,
                        category=SignalCategory.MCP_SERVER,
                        token_label="mcp_tool",
                        location=call.location,
                        scope=call.scope,
                        rationale_code="mcp_tool_pattern",
                        confidence=0.65,
                    )
                )
            if _MULTI_AGENT.search(blob):
                evidence.append(
                    build_evidence(
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        evidence_kind=EvidenceKind.PROMPT_TEMPLATE,
                        category=SignalCategory.AGENT_FRAMEWORK,
                        token_label="multi_agent",
                        location=call.location,
                        scope=call.scope,
                        rationale_code="multi_agent_pattern",
                        confidence=0.7,
                    )
                )

        for cfg in features.configs:
            loc = cfg.location.replace("\\", "/")
            name = loc.rsplit("/", 1)[-1]
            if name in {".mcp.json", "mcp.json"} or "mcp" in cfg.key.lower():
                evidence.append(
                    build_evidence(
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        evidence_kind=EvidenceKind.DEPENDENCY,
                        category=SignalCategory.MCP_SERVER,
                        token_label="mcp_config",
                        location=cfg.location,
                        scope=cfg.scope,
                        rationale_code="mcp_config_file",
                        confidence=0.8,
                    )
                )

        for pkg in features.packages:
            if _MCP_IMPORT.search(pkg.name):
                evidence.append(
                    build_evidence(
                        detector_id=self.detector_id,
                        detector_version=self.detector_version,
                        evidence_kind=EvidenceKind.DEPENDENCY,
                        category=SignalCategory.MCP_SERVER,
                        token_label="mcp_package",
                        location=pkg.location,
                        scope=pkg.scope,
                        rationale_code="mcp_package",
                        confidence=0.85,
                        reachability=Reachability.MANIFEST_ONLY,
                    )
                )

        return evidence
