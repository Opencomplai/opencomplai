"""Annex III area leads in scan and check output (kept out of main.py).

A lead is a pointer for a person to review, never a finding: it has no
severity, never changes an exit code and is never part of the signed
artifact. The matcher runs in the core scan engine; this module decides
whether to ask for leads and how to print them.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Mapping
from typing import Final

from opencomplai_core.models import CorroborationReport
from rich.console import Console
from rich.markup import escape

INSTALL_HINT: Final = (
    "Annex III area leads (areas 3 to 8) need the optional plugin: "
    "pip install opencomplai-ai"
)

# Source: round decisions on the leads tier and on classification from code.
# Confidence: low. Needs founder review: yes (compliance content as data).
PROPOSAL_LEAD_NOTE: Final = (
    "A lead is a pointer for a person to review: not a finding and not a "
    "classification. The declared purpose stays authoritative."
)
PROPOSAL_LEAD_NOTE_DATA: Final = {
    "source": "round decisions on the leads tier and on classification from code, spec wording",
    "confidence": "low",
    "needs_founder_review": True,
}

LEADS_HEADING: Final = "Annex III area leads (for a person to review, not findings)"

# Source: round decision on the leads floor, heuristic. Confidence: low.
# Needs founder review: yes. On by default when the pool of areas other than 5
# keeps the precision of the training intent path (22 of 30) on the three
# labelled sets of the benchmark page.
LEADS_DEFAULT_ON: Final = True
# Source: round decision on the leads floor, heuristic. Confidence: low.
# Needs founder review: yes. Areas with no true positive on the three labelled
# sets, or pooled precision below the floor; area 5 is shown at the lowest
# confidence instead. These get the coverage notice only.
NOTICE_ONLY_AREAS: Final[frozenset[int]] = frozenset({7})


def plugin_installed() -> bool:
    try:
        return importlib.util.find_spec("opencomplai_ai") is not None
    except (ImportError, ValueError):
        return False


def leads_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """``OPENCOMPLAI_LEADS`` 1/true/on or 0/false/off; anything else: the default."""
    value = (os.environ if environ is None else environ).get("OPENCOMPLAI_LEADS", "")
    value = value.strip().lower()
    if value in {"1", "true", "on"}:
        return True
    if value in {"0", "false", "off"}:
        return False
    return LEADS_DEFAULT_ON


def want_leads(ai_intent: bool, ai_legacy: bool, propose: bool) -> bool:
    """Leads are the default-path side channel; findings supersede them."""
    return leads_enabled() and not (ai_intent or ai_legacy or propose)


def lead_areas(ai_intent: bool, ai_legacy: bool, propose: bool) -> frozenset[int]:
    if not want_leads(ai_intent, ai_legacy, propose) or not plugin_installed():
        return frozenset()
    return frozenset(range(3, 9)) - NOTICE_ONLY_AREAS


def render_leads(
    console: Console,
    report: CorroborationReport,
    area_labels: dict[int | None, str],
    limit: int = 10,
) -> None:
    summary = report.eu_ai_scan
    leads = summary.proposal_leads if summary is not None else []
    if not leads:
        return
    console.print(f"\n[bold]{LEADS_HEADING}[/bold]")
    for lead in leads[:limit]:
        label = area_labels.get(lead.annex_iii_area, str(lead.annex_iii_area))
        mark = "  lowest confidence" if lead.annex_iii_area == 5 else ""
        console.print(
            f"  - {escape(f'{lead.file}:{lead.line}')}  {escape(lead.function)}  "
            f"{escape(label)}  {lead.confidence_band}{mark}",
            soft_wrap=True,
        )
    if len(leads) > limit:
        console.print(f"  ... and {len(leads) - limit} more")
    console.print(f"  [dim]{PROPOSAL_LEAD_NOTE}[/dim]", soft_wrap=True)
