"""Annex III area leads from the deterministic matcher.

A lead is a pointer for a person, never a finding: it is built from the intent
matcher's evidence after the default scan has finished, so it cannot reach the
evidence list, the proposal, the counts, the hashes or any exit code. Pure and
plugin-free: the matcher itself runs in ``scan_engine`` and hands its evidence
here. The band is a count-free heuristic from how the signal matched.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal, cast

from opencomplai_core.knowledge.annex_iii import ANNEX_III
from opencomplai_core.models import EuAiProposalLead, EvidenceItem

# Compliance content as data: the founder reviews the band rules.
LEAD_BAND_RULES: dict[str, Any] = {
    "source": "round decision on the leads floor, heuristic",
    "confidence": "low",
    "needs_founder_review": True,
    # shown, but always the lowest band
    "lowest_areas": frozenset({5}),
    # a signal listed in the area's code_signals
    "code_signal_band": "medium",
    # a keyword substring only
    "keyword_band": "low",
    # "high" is never produced
}

LeadBand = Literal["low", "medium", "high"]

_AREA_CODE_SIGNALS: dict[int, frozenset[str]] = {}
for _entry in ANNEX_III:
    _AREA_CODE_SIGNALS[_entry.area] = _AREA_CODE_SIGNALS.get(
        _entry.area, frozenset()
    ) | frozenset(_entry.code_signals)


def lead_band(area: int, signals: Iterable[str]) -> LeadBand:
    if area in LEAD_BAND_RULES["lowest_areas"]:
        return "low"
    known = _AREA_CODE_SIGNALS.get(area, frozenset())
    if any(s in known for s in signals):
        return cast(LeadBand, LEAD_BAND_RULES["code_signal_band"])
    return cast(LeadBand, LEAD_BAND_RULES["keyword_band"])


def leads_from_evidence(
    evidence: Iterable[EvidenceItem], areas: Iterable[int]
) -> list[EuAiProposalLead]:
    """One lead per call site that the matcher put in one of ``areas``.

    ``areas`` is always a subset of 3..8. A declared-purpose echo
    (``declared_purpose_used``) is the manifest talking back, not code, and is
    left out.
    """
    wanted = frozenset(areas)
    out: dict[tuple[str, int, str, int], EuAiProposalLead] = {}
    for ev in evidence:
        ann = getattr(ev, "intent_annotation", None)
        if ann is None or not ev.locations:
            continue
        area = getattr(ann, "annex_iii_area", None)
        if (
            getattr(ann, "risk_tier", None) != "high_risk"
            or area not in wanted
            or getattr(ann, "declared_purpose_used", False)
        ):
            continue
        file, _, line = ev.locations[0].rpartition(":")
        if not file or not line.isdigit() or int(line) < 1:
            continue
        signals = list(getattr(ann, "matched_signals", []) or [])
        out[(file, int(line), ev.token_label, area)] = EuAiProposalLead(
            file=file,
            line=int(line),
            function=ev.token_label,
            annex_iii_area=area,
            confidence_band=lead_band(area, signals),
            signals=signals,
        )
    return [out[k] for k in sorted(out)]
