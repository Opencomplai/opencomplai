"""Imported-but-unclassified AI libraries, reported as candidates.

A candidate is a lead for a person, never a finding: it is built from the raw
import list after the intent path has finished, so it cannot reach the
evidence list, the proposal, the counts, the hashes or any exit code. The
vocabulary lives here (not in ``ai_signals.json``) so default-path behaviour
cannot move.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from opencomplai_core.models import (
    CANDIDATE_REASON_IMPORTED_NOT_CLASSIFIED,
    EuAiCandidate,
    EvidenceScope,
)
from opencomplai_core.scanner.detectors._signals import load_signals
from opencomplai_core.scanner.feature_types import ImportRef

_EXTRA_SOURCE = "candidate vocabulary; public issue 90"
_DICTIONARY_SOURCE = "ai_signals.json#biometric"


@dataclass(frozen=True)
class CandidateLibrary:
    module: str
    source: str
    confidence: str
    needs_founder_review: bool


# cv2 is the module of the PyPI distribution ``opencv-python``; mediapipe (pose)
# is already in the ``ml_frameworks`` group but yields no classification.
EXTRA_LIBRARIES: tuple[CandidateLibrary, ...] = tuple(
    CandidateLibrary(m, _EXTRA_SOURCE, "medium", True)
    for m in ("retinaface", "cv2", "dlib", "mtcnn", "facenet_pytorch", "mediapipe")
)


def candidate_modules() -> dict[str, CandidateLibrary]:
    """Module root -> record. An extra wins over a dictionary token of the same name."""
    out = {
        token.lower(): CandidateLibrary(
            token.lower(), _DICTIONARY_SOURCE, "medium", True
        )
        for token in load_signals().get("biometric", [])
    }
    out.update({lib.module: lib for lib in EXTRA_LIBRARIES})
    return out


def find_import_candidates(
    imports: Iterable[ImportRef], finding_locations: Iterable[str]
) -> list[EuAiCandidate]:
    """One candidate per (library, file): production-scope imports of a known
    library that carry no finding at that location."""
    known = candidate_modules()
    covered = set(finding_locations)
    best: dict[tuple[str, str], int] = {}
    for ref in imports:
        if ref.scope != EvidenceScope.PROD or ref.location in covered:
            continue
        root = ref.module.lower().split(".")[0]
        if root not in known:
            continue
        file, _, line_text = ref.location.rpartition(":")
        if not file or not line_text.isdecimal() or int(line_text) < 1:
            continue
        key = (ref.module.split(".")[0], file)
        line = int(line_text)
        if key not in best or line < best[key]:
            best[key] = line
    return [
        EuAiCandidate(
            library=library,
            file=file,
            line=line,
            reason=CANDIDATE_REASON_IMPORTED_NOT_CLASSIFIED,
        )
        for (library, file), line in sorted(
            best.items(), key=lambda kv: (kv[0][1], kv[1], kv[0][0])
        )
    ]
