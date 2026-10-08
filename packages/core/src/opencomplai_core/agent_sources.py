"""Gap rows for Art. 12, 14, 15 and 26 from the declared agent inventory (no I/O).

The manifest's agent inventory is the provider's own statement, so a row built
from it is PARTIAL at most and never MET. A scan finding is a heuristic and is
used only to cross-check the declaration (an agent framework the scan sees but
the inventory does not declare is a gap); it never produces MET either.

Row text carries counts and a fixed vocabulary only: declared agent ids, tool
names and model names never reach a gap row (they reach the dashboard).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    ConfidenceLabel,
    CorroborationReport,
    EvidenceScope,
    GapStatus,
    SignalCategory,
    SystemManifest,
)

AGENT_SOURCE_REF = "agent_declarations"
AGENT_ARTICLES = ("Art. 12", "Art. 14", "Art. 15", "Art. 26")

# E-15: the ceiling, the MISSING choices and the heuristics are the founder's
# and the lawyer's to approve.
NEEDS_REVIEW_NOTES: dict[str, dict] = {
    AGENT_SOURCE_REF: {
        "source": (
            "Regulation (EU) 2024/1689 Art. 12, 14, 15, 26; manifest declaration "
            "cross-checked with scanner findings, not independently verified"
        ),
        "confidence": "low",
        "needs_founder_review": True,
        "note": (
            "A declaration reads PARTIAL at most and is never MET. An agent "
            "framework or MCP server the scan finds but the inventory does not "
            "declare reads MISSING, as does an incomplete declaration. Findings "
            "in test, docs, generated or vendor scope are ignored, and provider "
            "names are matched by case-insensitive containment. All of this is "
            "heuristic and needs approval."
        ),
    }
}

_AGENT_FRAMEWORK = "agent framework"
_MCP_SERVER = "MCP server"
_PROVIDER = "model provider"
# Scopes that do not ship; a finding there says nothing about the system.
_NON_SHIPPING = {
    EvidenceScope.TEST,
    EvidenceScope.DOCS,
    EvidenceScope.GENERATED,
    EvidenceScope.VENDOR,
}


@dataclass(frozen=True)
class Detected:
    frameworks: bool = False
    mcp: bool = False
    providers: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class CrossCheck:
    undeclared: list[str]
    unseen: list[str]


def detected(report: CorroborationReport) -> Detected:
    tokens = {e.evidence_id: e.token_label for e in report.evidence}
    frameworks = mcp = False
    providers: set[str] = set()
    for f in report.findings:
        if f.scope in _NON_SHIPPING:
            continue
        if f.signal_category == SignalCategory.AGENT_FRAMEWORK:
            frameworks = True
        elif f.signal_category == SignalCategory.MCP_SERVER:
            mcp = True
        elif f.signal_category == SignalCategory.AI_SDK:
            providers.update(
                tokens[i].casefold() for i in f.evidence_ids if tokens.get(i)
            )
    return Detected(frameworks, mcp, frozenset(providers))


def _same_provider(token: str, declared: str) -> bool:
    return token in declared or declared in token


def cross_check(inventory, found: Detected) -> CrossCheck:
    """Heuristic declared-versus-detected comparison; labels are a fixed vocabulary."""
    undeclared: list[str] = []
    unseen: list[str] = []
    has_mcp_tool = any(t.kind == "mcp" for a in inventory.agents for t in a.tools)
    if found.frameworks and not inventory.agents:
        undeclared.append(_AGENT_FRAMEWORK)
    elif inventory.agents and not found.frameworks:
        unseen.append(_AGENT_FRAMEWORK)
    if found.mcp and not has_mcp_tool:
        undeclared.append(_MCP_SERVER)
    elif has_mcp_tool and not found.mcp:
        unseen.append(_MCP_SERVER)
    declared = {m.provider.casefold() for a in inventory.agents for m in a.models}
    undeclared += sorted(
        t for t in found.providers if not any(_same_provider(t, d) for d in declared)
    )
    if any(not any(_same_provider(t, d) for t in found.providers) for d in declared):
        unseen.append(_PROVIDER)
    return CrossCheck(undeclared, unseen)


def _incomplete(article: str, manifest: SystemManifest, agents) -> str | None:
    """Why the declaration does not cover the article, or None when it does."""
    if article == "Art. 12":
        if any(not (a.logging and a.logging.decision_log_ref) for a in agents):
            return "an agent declares no decision log reference"
    elif article == "Art. 14":
        oversight = getattr(manifest, "human_oversight", None)
        can = oversight is not None and any(r.can_intervene for r in oversight.roles)
        if any(t.requires_approval for a in agents for t in a.tools) and not can:
            return "a tool requires approval but no oversight role can intervene"
    elif article == "Art. 15":
        if any(not a.guardrails for a in agents):
            return "an agent declares no guardrail"
    elif article == "Art. 26":
        if any(not (a.mandate and a.mandate.permitted_actions) for a in agents):
            return "an agent declares no mandate with permitted actions"
    return None


def agent_gap_status(
    article: str, manifest: SystemManifest, report: CorroborationReport | None
) -> ArticleGapStatus | None:
    """The row for one agent article, or None (other article, or no inventory)."""
    inventory = getattr(manifest, "agent_inventory", None)
    if article not in AGENT_ARTICLES or inventory is None:
        return None
    agents = inventory.agents
    tools = [t for a in agents for t in a.tools]
    # Scan evidence from a supplied report only: with none, nothing is invented.
    check = cross_check(inventory, detected(report)) if report is not None else None
    undeclared = check.undeclared if check else []
    incomplete = _incomplete(article, manifest, agents)

    text = (
        f"Agent inventory declared in the manifest: {len(agents)} agent(s), "
        f"{len(tools)} tool(s), {sum(bool(t.requires_approval) for t in tools)} "
        "requiring approval."
    )
    if check is None:
        text += " No scan report supplied; the declaration was not cross-checked."
    else:
        text += (
            f" Detected but not declared: {', '.join(undeclared) or 'none'}."
            f" Declared but not detected: {', '.join(check.unseen) or 'none'}."
        )
    if incomplete:
        text += f" Declaration incomplete for {article}: {incomplete}."
    text += " A declaration only; not verified against the system."

    heuristic = any(u in (_AGENT_FRAMEWORK, _MCP_SERVER) for u in undeclared)
    # Never MET: a declaration is not evidence and a scan finding is a heuristic.
    status = GapStatus.MISSING if heuristic or incomplete else GapStatus.PARTIAL
    return ArticleGapStatus(
        article="",
        status=status,
        source=ArticleGapSource.MANIFEST,
        evidence_ref=f"manifest:{AGENT_SOURCE_REF}",
        rationale=text,
        confidence=0.6 if heuristic else None,
        confidence_label=(
            ConfidenceLabel.HEURISTIC_ESTIMATE
            if heuristic
            else ConfidenceLabel.NOT_ASSESSED
        ),
    )
