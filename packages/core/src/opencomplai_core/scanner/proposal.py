"""Aggregate call-site findings into one system-level classification proposal.

A ``--ai-intent`` scan reports one regulatory finding per call site. This module
answers the next question: which Annex III area do those call sites most often
point to, if any? The result is a *proposal from code*. It is not a legal
classification, it is never confirmed here, and no verdict, severity or exit code
reads it. The declared purpose stays authoritative.

Pure and deterministic: no clock, no randomness, no file system, no plugin
import (``opencomplai_ai`` is optional, so the bridge test lives in that package).
"""

from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel, Field

from opencomplai_core.knowledge.annex_iii import lookup_by_area
from opencomplai_core.models import EuAiRegulatoryFinding, EuAiScanSummary

# Compliance content as data (decision E-9): a heuristic, not a probability.
CONFIDENCE_LABEL_BANDS: dict = {
    "source": "CL-C2 spec heuristic",
    "confidence": "low",
    "needs_founder_review": True,
    # (min_count, max_count or None, label), checked in order.
    "bands": (
        (0, 0, "none"),
        (1, 1, "low"),
        (2, 3, "medium"),
        (4, None, "high"),
    ),
}

CONFIDENCE_BASIS = (
    "Label from the number of distinct call sites that support the area; "
    "it is a count, not a probability."
)

_STANDING_NOTE = (
    "Proposal from code signals only. It is not a legal classification and is "
    "not confirmed by a person; the declared purpose stays authoritative."
)


class ProposalEvidenceLine(BaseModel):
    location: str
    file: str
    line: int | None = None
    function: str
    annex_iii_area: int | None = None
    risk_tier: str
    signals: list[str] = Field(default_factory=list)
    entry_title: str | None = None
    regulation_ref: str = ""


class ClassificationProposal(BaseModel):
    proposed_annex_iii_area: int | None = None
    proposed_area_name: str | None = None
    confidence_label: Literal["none", "low", "medium", "high"] = "none"
    confidence_basis: str = CONFIDENCE_BASIS
    supporting_count: int = 0
    supporting_evidence: list[ProposalEvidenceLine] = Field(default_factory=list)
    minority_evidence: list[ProposalEvidenceLine] = Field(default_factory=list)
    prohibited_signals: list[ProposalEvidenceLine] = Field(default_factory=list)
    declared_purpose_echo: list[ProposalEvidenceLine] = Field(default_factory=list)
    tie_areas: list[int] = Field(default_factory=list)
    confirmation_status: Literal["unconfirmed"] = "unconfirmed"
    needs_founder_review: bool = True
    notes: list[str] = Field(default_factory=list)


def _split_location(location: str) -> tuple[str, int | None]:
    head, sep, tail = location.rpartition(":")
    if sep and tail.isascii() and tail.isdigit():
        return head, int(tail)
    return location, None


def _evidence_line(finding: EuAiRegulatoryFinding) -> ProposalEvidenceLine:
    file, line = _split_location(finding.location)
    rationale = finding.rationale
    return ProposalEvidenceLine(
        location=finding.location,
        file=file,
        line=line,
        function=finding.function,
        annex_iii_area=finding.annex_iii_area,
        risk_tier=finding.risk_tier,
        signals=list(rationale.matched_signals) if rationale else [],
        entry_title=rationale.knowledge_entry_title if rationale else None,
        regulation_ref=rationale.regulation_ref if rationale else "",
    )


def _sort_key(line: ProposalEvidenceLine) -> tuple:
    # Trailing fields only break ties so shuffled input gives identical output.
    return (
        line.file,
        line.line or 0,
        line.function,
        line.location,
        line.annex_iii_area or 0,
    )


def _label_for(count: int) -> Literal["none", "low", "medium", "high"]:
    for low, high, label in CONFIDENCE_LABEL_BANDS["bands"]:
        if count >= low and (high is None or count <= high):
            return cast(Literal["none", "low", "medium", "high"], label)
    return "none"


def build_classification_proposal(
    summary: EuAiScanSummary | None,
) -> ClassificationProposal:
    """Return the most supported Annex III area (or none) for a scan summary."""
    high_risk = summary.high_risk if summary is not None else []
    prohibited = summary.prohibited if summary is not None else []

    prohibited_lines = sorted((_evidence_line(f) for f in prohibited), key=_sort_key)

    # Area-less findings support nothing. One call site counts once.
    candidates = sorted(
        (
            (_evidence_line(f), bool(f.rationale and f.rationale.declared_purpose_used))
            for f in high_risk
            if f.annex_iii_area is not None
        ),
        key=lambda pair: _sort_key(pair[0]),
    )
    seen: set[str] = set()
    echo: list[ProposalEvidenceLine] = []
    by_area: dict[int, list[ProposalEvidenceLine]] = {}
    for line, from_declaration in candidates:
        if line.location in seen:
            continue
        seen.add(line.location)
        if from_declaration:
            echo.append(line)
            continue
        area = line.annex_iii_area
        if area is None:  # unreachable: candidates are pre-filtered
            continue
        by_area.setdefault(area, []).append(line)

    notes = [_STANDING_NOTE]
    proposal = ClassificationProposal(
        prohibited_signals=prohibited_lines,
        declared_purpose_echo=echo,
    )

    if by_area:
        top = max(len(lines) for lines in by_area.values())
        winners = sorted(a for a, lines in by_area.items() if len(lines) == top)
        if len(winners) == 1:
            area = winners[0]
            entries = lookup_by_area(area)
            proposal.proposed_annex_iii_area = area
            proposal.proposed_area_name = entries[0].area_name if entries else None
            proposal.supporting_evidence = by_area[area]
            proposal.supporting_count = len(by_area[area])
            proposal.minority_evidence = sorted(
                (ln for a, lines in by_area.items() if a != area for ln in lines),
                key=_sort_key,
            )
            if proposal.minority_evidence:
                notes.append(
                    f"{len(proposal.minority_evidence)} call site(s) point to other "
                    "areas and are listed as minority evidence."
                )
        else:
            proposal.tie_areas = winners
            proposal.minority_evidence = sorted(
                (ln for lines in by_area.values() for ln in lines), key=_sort_key
            )
            notes.append(
                f"Areas {', '.join(str(a) for a in winners)} have equal support; "
                "no area is proposed."
            )
    else:
        notes.append("No call site supports an Annex III area.")

    if echo:
        notes.append(
            f"{len(echo)} finding(s) take their area from the declared purpose, "
            "not from code, and are not counted as support."
        )
    if prohibited_lines:
        notes.append(
            f"{len(prohibited_lines)} prohibited-practice signal(s) are listed "
            "for review; they do not change the proposed area."
        )

    proposal.confidence_label = _label_for(proposal.supporting_count)
    proposal.notes = notes
    return proposal
