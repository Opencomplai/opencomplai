"""EU AI Act machine-readable knowledge pack.

Single source of truth for Annex III high-risk areas, Art. 5 prohibited
practices, and Art. 50 limited-risk transparency triggers.  All scanner
components (rules.py, mapping.py, classifier.py, detector.py) import from
here so the regulation text and the scanner can never drift apart.
"""

from opencomplai_ai.knowledge.annex_iii import ANNEX_III, AnnexIIIEntry
from opencomplai_ai.knowledge.limited_risk import LIMITED_RISK, LimitedRiskEntry
from opencomplai_ai.knowledge.prohibited import PROHIBITED, ProhibitedEntry

__all__ = [
    "ANNEX_III",
    "LIMITED_RISK",
    "PROHIBITED",
    "AnnexIIIEntry",
    "LimitedRiskEntry",
    "ProhibitedEntry",
]
