"""Thin artifact/path probes for gap articles (Arts. 9, 13, 14, 16, 24, 43).

Convention-based file checks only — honest Partial/Unverified statuses preferred
over fake Met. Not a ComplianceAgent-style analyzer framework.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    ConfidenceLabel,
    GapStatus,
)

# Relative path globs (fnmatch-style via Path.rglob / name match)
_PROBE_PATTERNS: dict[str, tuple[str, ...]] = {
    "risk_register": (
        "risk_register.json",
        "risk-register.json",
        "docs/risk*",
        "docs/**/risk*",
    ),
    "deployer_instructions": (
        "docs/instructions*",
        "docs/**/instructions*",
        "INSTRUCTIONS.md",
        "DEPLOYER.md",
    ),
    "human_oversight_construct": (
        "**/human_oversight*",
        "**/oversight*",
        "docs/**/oversight*",
    ),
    "provider_qms_bundle": (
        "docs/qms*",
        "docs/**/quality*",
        "QMS.md",
        "QUALITY_MANAGEMENT.md",
    ),
    "distributor_conformity": (
        "docs/conformity*",
        "CONFORMITY*",
        "CE_MARKING*",
        "docs/**/distributor*",
    ),
    "conformity_assessment_docs": (
        "docs/conformity*",
        "CONFORMITY*",
        "docs/**/assessment*",
    ),
}

_CODE_HINTS: dict[str, re.Pattern[str]] = {
    "human_oversight_construct": re.compile(
        r"\b(human_in_the_loop|require_approval|hitl|human_oversight)\b",
        re.I,
    ),
}


@dataclass
class ProbeResult:
    found_paths: list[str]
    code_hits: int = 0


def _match_patterns(repo_root: Path, patterns: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    if not repo_root.is_dir():
        return found
    # Bound walk — only shallow-ish search for named stems
    for pattern in patterns:
        if "*" not in pattern and "/" not in pattern:
            candidate = repo_root / pattern
            if candidate.is_file():
                found.append(pattern)
            continue
        # Simple recursive name check without full glob explosion
        stem = pattern.replace("**/", "").replace("*", "")
        stem = stem.strip("/")
        if not stem:
            continue
        for path in repo_root.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(repo_root).as_posix()
            except ValueError:
                continue
            if len(rel) > 240:
                continue
            name = path.name.lower()
            if stem.lower() in name or stem.lower() in rel.lower():
                found.append(rel)
                if len(found) >= 5:
                    return found
    return found


def _scan_code_hints(repo_root: Path, pattern: re.Pattern[str]) -> int:
    hits = 0
    for path in repo_root.rglob("*.py"):
        try:
            if path.stat().st_size > 1_048_576:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if pattern.search(text):
            hits += 1
            if hits >= 3:
                break
    return hits


def run_artifact_probe(ref: str, repo_root: Path | None) -> ProbeResult:
    patterns = _PROBE_PATTERNS.get(ref, ())
    if repo_root is None or not patterns:
        return ProbeResult(found_paths=[])
    paths = _match_patterns(repo_root, patterns)
    code_hits = 0
    hint = _CODE_HINTS.get(ref)
    if hint is not None:
        code_hits = _scan_code_hints(repo_root, hint)
    return ProbeResult(found_paths=paths, code_hits=code_hits)


def artifact_gap_status(ref: str, repo_root: Path | None) -> ArticleGapStatus:
    """Map a probe ref to an honest gap row."""
    if repo_root is None:
        return ArticleGapStatus(
            article="",
            status=GapStatus.UNVERIFIED,
            source=ArticleGapSource.ARTIFACT,
            evidence_ref=ref,
            rationale=(
                f"Artifact probe '{ref}' not run (no repo root supplied). "
                "Pass --repo-root to evaluate documentation/code conventions."
            ),
            confidence=None,
            confidence_label=ConfidenceLabel.NOT_ASSESSED,
        )
    result = run_artifact_probe(ref, repo_root)
    if result.found_paths or result.code_hits:
        evidence = result.found_paths[0] if result.found_paths else f"code_hint:{ref}"
        return ArticleGapStatus(
            article="",
            status=GapStatus.PARTIAL,
            source=ArticleGapSource.ARTIFACT,
            evidence_ref=evidence,
            rationale=(
                f"Found candidate artifact/signal for '{ref}' "
                f"({len(result.found_paths)} path(s), {result.code_hits} code hint(s)). "
                "Heuristic only — not a full obligation assessment."
            ),
            confidence=0.55,
            confidence_label=ConfidenceLabel.HEURISTIC_ESTIMATE,
        )
    return ArticleGapStatus(
        article="",
        status=GapStatus.MISSING,
        source=ArticleGapSource.ARTIFACT,
        evidence_ref=ref,
        rationale=(
            f"No conventional documentation/code probe matched for '{ref}'. "
            "Add the expected file or construct, then re-run gaps."
        ),
        confidence=0.4,
        confidence_label=ConfidenceLabel.HEURISTIC_ESTIMATE,
    )
