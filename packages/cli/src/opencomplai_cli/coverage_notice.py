"""What the default scan covers, as data and as a short text notice.

A statement about the tool, not a classification and not a verdict. The area
statuses are derived from the shipped signal dictionary, never listed by hand.
"""

from __future__ import annotations

from typing import Any

from opencomplai_core.models import CorroborationReport
from opencomplai_core.scanner.detectors._signals import load_signals
from opencomplai_core.scanner.mapping import _AREA_TO_TAXONOMY

_FLAGS = ["--ai-intent", "--propose"]


def default_scan_coverage(*, intent_analysis_ran: bool) -> dict[str, Any]:
    signals = load_signals()
    area_signals = signals.get("area_signals", {})
    areas: dict[str, str] = {}
    for area, key in _AREA_TO_TAXONOMY.items():
        if area == 1 and signals.get("biometric"):
            status = "default_tokens"
        elif area != 1 and area_signals.get(key):
            status = "partial_tokens"
        else:
            status = "not_covered"
        areas[str(area)] = status
    return {
        "version": 1,
        "areas": areas,
        "reached_by": list(_FLAGS),
        "intent_analysis_ran": intent_analysis_ran,
        "note": "Statement about the default scan; not a compliance verdict.",
    }


def notice_lines(report: CorroborationReport) -> list[str]:
    cov = report.default_scan_coverage
    if not cov or cov.get("intent_analysis_ran"):
        return []
    areas: dict[str, str] = cov.get("areas", {})
    read = [
        _AREA_TO_TAXONOMY[int(a)]
        for a, st in areas.items()
        if st != "not_covered" and int(a) in _AREA_TO_TAXONOMY
    ]
    missing = sorted(int(a) for a, st in areas.items() if st == "not_covered")
    parts = [
        "\n  What the default scan covers: its signal dictionary reads "
        + (", ".join(read) or "no Annex III area")
        + " (Annex III areas "
        + ", ".join(
            str(a)
            for a in sorted(int(a) for a, st in areas.items() if st != "not_covered")
        )
        + ")."
    ]
    if missing:
        parts.append(
            "Annex III areas "
            + ", ".join(str(a) for a in missing)
            + " are not reached by that dictionary."
        )
    parts.append(
        "A quiet result is not evidence that no area applies. "
        f"Run with {' or '.join(cov.get('reached_by', _FLAGS))} to examine them."
    )
    return [" ".join(parts)]
