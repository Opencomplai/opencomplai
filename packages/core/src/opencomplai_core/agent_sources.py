"""Gap rows for Art. 12, 14, 15 and 26 from the declared agent inventory (no I/O
except an existence check of declared evidence paths under repo_root; the clock
is passed in).

The manifest's agent inventory is the provider's own statement, so a row built
from it is PARTIAL at most and never MET. A scan finding is a heuristic and is
used only to cross-check the declaration (an agent framework the scan sees but
the inventory does not declare is a gap); it never produces MET either.

Row text carries counts and a fixed vocabulary only: declared agent ids, tool
names and model names never reach a gap row (they reach the dashboard).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

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
            "heuristic and needs approval. An expired mandate (UTC calendar-date "
            "comparison) or an absent or out-of-repo guardrail evidence file also "
            "reads MISSING; the date rule and the path rule are heuristics needing "
            "approval."
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


def _expired(expires_at: str | None, today: date) -> bool:
    """True when the mandate expiry date (UTC) is before today; None never expires."""
    if expires_at is None:
        return False
    try:
        dt = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return dt.date() < today


def _evidence_missing(repo_root: Path, ref: str) -> bool:
    """True when a file-path evidence ref is blank, absent or outside the repo."""
    if "://" in ref:
        return False
    if not ref.strip():
        return True
    try:
        root = repo_root.resolve()
        target = (root / ref).resolve()
        return not target.is_relative_to(root) or not target.exists()
    except (OSError, ValueError):
        return True


def _incomplete(
    article: str,
    manifest: SystemManifest,
    agents,
    *,
    today: date | None = None,
    repo_root: Path | None = None,
) -> str | None:
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
        if repo_root is not None and any(
            g.evidence_ref is not None and _evidence_missing(repo_root, g.evidence_ref)
            for a in agents
            for g in a.guardrails
        ):
            return "a guardrail evidence file is missing or outside the repository"
    elif article == "Art. 26":
        if any(not (a.mandate and a.mandate.permitted_actions) for a in agents):
            return "an agent declares no mandate with permitted actions"
        if today is not None and any(
            _expired(a.mandate.expires_at, today) for a in agents
        ):
            return "an agent mandate has expired"
    return None


def agent_gap_status(
    article: str,
    manifest: SystemManifest,
    report: CorroborationReport | None,
    *,
    today: date | None = None,
    repo_root: Path | None = None,
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
    incomplete = _incomplete(
        article, manifest, agents, today=today, repo_root=repo_root
    )

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
