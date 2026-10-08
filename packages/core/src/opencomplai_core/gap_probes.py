"""Thin artifact/path probes for gap articles (Arts. 9, 11, 13, 14, 16, 17, 24, 26, 43, 49, 50, 53, 55).

Convention-based file checks only — honest Partial/Unverified statuses preferred
over fake Met. Not a ComplianceAgent-style analyzer framework. The probes are
file-name conventions, not legal tests: presence of a file is never proof of
compliance, so these rows reach Partial at most.
"""

from __future__ import annotations

import functools
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    ConfidenceLabel,
    GapStatus,
)

# Placeholder evidence slots, reserved so a real probe can later replace a stub
# without editing the article map. A stub is never a candidate: the
# source loop in gap_report.py skips it, so it cannot create a verdict (an
# unregistered artifact ref would otherwise read MISSING).
STUB_SOURCE_REFS: dict[str, frozenset[str]] = {
    "artifact": frozenset(),
    "manifest": frozenset(
        {
            "instructions_for_use_fields",  # Art. 13 manifest slot; no probe reads it yet
        }
    ),
}

# source/confidence/needs_founder_review for the probes added with real sources
# and for evaluator refs (E-15). New probes add their own entries.
PROBE_PROVENANCE: dict[str, dict] = {
    "technical_documentation_dossier": {
        "source": "Reg. (EU) 2024/1689 Art. 11 and Annex IV (text unverified here); "
        "dossier_<id>.json written by the CLI dossier command",
        "confidence": "medium",
        "needs_founder_review": True,
    },
    "transparency_notice_evidence": {
        "source": "Reg. (EU) 2024/1689 Art. 50 (text unverified here); "
        "file names written by `recommend` plus common disclosure names",
        "confidence": "low",
        "needs_founder_review": True,
    },
    "eu_database_registration_evidence": {
        "source": "Reg. (EU) 2024/1689 Art. 49 (text unverified here); "
        "file-name convention only",
        "confidence": "low",
        "needs_founder_review": True,
    },
    "deployer_use_records": {
        "source": "Reg. (EU) 2024/1689 Art. 26 (text unverified here); "
        "file-name convention only",
        "confidence": "low",
        "needs_founder_review": True,
    },
    "post_market_monitoring_plan": {
        "source": "Reg. (EU) 2024/1689 Art. 72 (text unverified here); "
        "file-name convention plus heuristic content keywords",
        "confidence": "low",
        "needs_founder_review": True,
    },
    "serious_incident_log": {
        "source": "Reg. (EU) 2024/1689 Art. 73 (text unverified here); "
        "root incident-log.json with a signed-log line (heuristic marker)",
        "confidence": "low",
        "needs_founder_review": True,
    },
    "deployer_instructions": {
        "source": "heuristic (no legal source): Art. 13(3) topic keywords in the "
        "instructions file",
        "confidence": "low",
        "needs_founder_review": True,
    },
    "event_log_evidence": {
        "source": "Regulation (EU) 2024/1689 Art. 12; presence of a chained log "
        "file (oversight log or agent decision log), contents not verified by "
        "the probe",
        "confidence": "low",
        "needs_founder_review": True,
    },
    "gpai_model_documentation": {
        "source": "Reg. (EU) 2024/1689 Art. 53 and Annex XI (text unverified "
        "here); file-name convention only",
        "confidence": "low",
        "needs_founder_review": True,
    },
    "gpai_downstream_information": {
        "source": "Reg. (EU) 2024/1689 Art. 53 and Annex XII (text unverified "
        "here); file-name convention only",
        "confidence": "low",
        "needs_founder_review": True,
    },
    "gpai_systemic_risk_evaluation": {
        "source": "Reg. (EU) 2024/1689 Art. 55 and Annex XI Section 2 (text "
        "unverified here); file-name convention only",
        "confidence": "low",
        "needs_founder_review": True,
    },
    "EVAL_ADVERSARIAL_V1": {
        "source": "heuristic (no legal source): deterministic lexical signature "
        "match; the evaluator's own reference is NIST AI RMF MEASURE 2.7 / EU AI "
        "Act Art. 15 (text unverified here)",
        "confidence": "low",
        "needs_founder_review": True,
    },
}

# Root file the serious-incident log lives in (a signed log written by the
# `incident` commands). Defined once: the probes below reference this constant, never the literal.
INCIDENT_LOG_PATH = "incident-log.json"

# Relative path globs (fnmatch-style via Path.rglob / name match)
_PROBE_PATTERNS: dict[str, tuple[str, ...]] = {
    # `**/` so a dossier in the repo root and one in a subfolder both match.
    "technical_documentation_dossier": ("**/dossier_*.json",),
    # Not transparency_notice* (the Art. 13 file) and not bare "transparency".
    "transparency_notice_evidence": (
        "**/art50-transparency_middleware*",
        "**/ai-disclosure*",
        "AI_DISCLOSURE.md",
    ),
    "eu_database_registration_evidence": (
        "**/eu-database*",
        "**/eu_database*",
        "EU_DATABASE_REGISTRATION.md",
        "**/art49-registration*",
    ),
    "deployer_use_records": (
        "**/deployer-use-log*",
        "**/deployer_use_log*",
        "**/use-records*",
        "DEPLOYER_USE_RECORDS.md",
    ),
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
        "docs/provider-obligations*",
        "docs/**/provider*",
        "PROVIDER_OBLIGATIONS.md",
        "docs/**/technical-documentation*",
    ),
    "provider_qms": (
        "docs/qms*",
        "docs/qms/**",
        "docs/**/quality*",
        "QMS.md",
        "QUALITY_MANAGEMENT.md",
        "docs/**/quality-management*",
    ),
    # GPAI documentation conventions (Art. 53 / Art. 55). Stems do not
    # overlap, so one probe never matches another's file.
    "gpai_model_documentation": (  # Annex XI
        "docs/gpai/model-documentation*",
        "docs/**/gpai-model-documentation*",
        "GPAI_MODEL_DOCUMENTATION.md",
    ),
    "gpai_downstream_information": (  # Annex XII
        "docs/gpai/downstream-information*",
        "docs/**/downstream-provider-information*",
        "GPAI_DOWNSTREAM_INFORMATION.md",
    ),
    "gpai_systemic_risk_evaluation": (  # Annex XI Section 2 / Art. 55
        "docs/gpai/systemic-risk*",
        "docs/**/adversarial-testing*",
        "GPAI_SYSTEMIC_RISK.md",
    ),
    "provider_fria": (
        "docs/fria*",
        "docs/**/fria*",
        "FRIA.md",
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
    # Art. 72 / Art. 73 evidence.
    "post_market_monitoring_plan": (
        "docs/post-market-monitoring-plan*",
        "docs/qms/post-market-monitoring*",
        "docs/**/post-market-monitoring*",
        "POST_MARKET_MONITORING_PLAN.md",
        "POST_MARKET_MONITORING.md",
    ),
    "serious_incident_log": (INCIDENT_LOG_PATH,),
    # Art. 12: the oversight log `approve`/`resume` write. Found only when
    # it sits inside the repo, e.g. OPENCOMPLAI_STATE_DIR=.opencomplai in CI or a
    # committed exported copy. File presence only: Partial at most, never Met.
    "event_log_evidence": ("**/oversight-log.json", "**/agent-log.jsonl"),
    # Art. 17(1)(a)-(m) per-clause probes. `provider_qms` above stays as the
    # whole-article convenience probe; these are narrower, clause-appropriate
    # glob sets so a partially-documented QMS shows which sub-points are
    # actually covered instead of one pass/fail for the whole article.
    "provider_qms_17_1_a": (  # (a) regulatory-compliance strategy
        "docs/qms/regulatory-compliance-strategy*",
        "docs/**/regulatory-compliance*",
        "docs/**/compliance-strategy*",
        "REGULATORY_COMPLIANCE_STRATEGY.md",
    ),
    "provider_qms_17_1_b": (  # (b) design and design-control procedures
        "docs/qms/design-control*",
        "docs/**/design-control*",
        "docs/**/design-verification*",
        "DESIGN_CONTROL.md",
    ),
    "provider_qms_17_1_c": (  # (c) development, QC and QA procedures
        "docs/qms/quality-management-procedures*",
        "docs/**/quality-assurance*",
        "docs/**/quality-control*",
        "QUALITY_MANAGEMENT_PROCEDURES.md",
    ),
    "provider_qms_17_1_d": (  # (d) examination, test and validation procedures
        "docs/qms/testing-validation*",
        "docs/**/test-validation*",
        "docs/**/validation-procedures*",
        "TESTING_VALIDATION.md",
    ),
    "provider_qms_17_1_e": (  # (e) technical specifications / harmonised standards
        "docs/qms/technical-documentation*",
        "docs/**/technical-specifications*",
        "docs/**/harmonised-standards*",
        "TECHNICAL_DOCUMENTATION.md",
    ),
    "provider_qms_17_1_f": (  # (f) data-management systems and procedures
        "docs/qms/data-governance*",
        "docs/**/data-governance*",
        "docs/**/data-management*",
        "DATA_GOVERNANCE.md",
    ),
    "provider_qms_17_1_g": (  # (g) risk-management system (Art. 9)
        "docs/qms/risk-management-system*",
        "docs/**/risk-management-system*",
        "RISK_MANAGEMENT_SYSTEM.md",
    ),
    "provider_qms_17_1_h": (  # (h) post-market monitoring system (Art. 72)
        "docs/qms/post-market-monitoring*",
        "docs/**/post-market-monitoring*",
        "POST_MARKET_MONITORING.md",
        INCIDENT_LOG_PATH,
    ),
    "provider_qms_17_1_i": (  # (i) serious-incident reporting (Art. 73)
        "docs/qms/serious-incident-reporting*",
        "docs/**/incident-reporting*",
        "docs/**/serious-incident*",
        "INCIDENT_REPORTING.md",
        INCIDENT_LOG_PATH,
    ),
    "provider_qms_17_1_j": (  # (j) communication with competent authorities/actors
        "docs/qms/regulatory-communication*",
        "docs/**/regulatory-communication*",
        "docs/**/transparency*",
        "TRANSPARENCY.md",
    ),
    "provider_qms_17_1_k": (  # (k) record-keeping of documentation/communication
        "docs/qms/record-keeping*",
        "docs/**/record-keeping*",
        "RECORD_KEEPING.md",
    ),
    "provider_qms_17_1_l": (  # (l) resource management, incl. security of supply
        "docs/qms/resource-management*",
        "docs/**/resource-management*",
        "docs/**/security-of-supply*",
        "RESOURCE_MANAGEMENT.md",
    ),
    "provider_qms_17_1_m": (  # (m) accountability framework
        "docs/qms/accountability-framework*",
        "docs/**/accountability*",
        "ACCOUNTABILITY_FRAMEWORK.md",
    ),
}

# Art. 17(1)(a)-(m), in article order — (clause letter, probe ref, short title).
# Both the qms_outline.md template renderer and the CLI reuse this single
# ordered list instead of hard-coding the 13 clauses twice.
QMS_17_1_CLAUSES: tuple[tuple[str, str, str], ...] = (
    ("a", "provider_qms_17_1_a", "Regulatory-compliance strategy"),
    ("b", "provider_qms_17_1_b", "Design and design-control procedures"),
    ("c", "provider_qms_17_1_c", "Development, QC and QA procedures"),
    ("d", "provider_qms_17_1_d", "Testing and validation procedures"),
    ("e", "provider_qms_17_1_e", "Technical specifications and standards applied"),
    ("f", "provider_qms_17_1_f", "Data-management systems and procedures"),
    ("g", "provider_qms_17_1_g", "Risk-management system (Art. 9)"),
    ("h", "provider_qms_17_1_h", "Post-market monitoring system (Art. 72)"),
    ("i", "provider_qms_17_1_i", "Serious-incident reporting procedures (Art. 73)"),
    ("j", "provider_qms_17_1_j", "Communication with national competent authorities"),
    ("k", "provider_qms_17_1_k", "Record-keeping of relevant documentation"),
    ("l", "provider_qms_17_1_l", "Resource management, incl. security of supply"),
    ("m", "provider_qms_17_1_m", "Accountability framework"),
)

_CODE_HINTS: dict[str, re.Pattern[str]] = {
    "human_oversight_construct": re.compile(
        r"\b(human_in_the_loop|require_approval|hitl|human_oversight)\b",
        re.I,
    ),
}

# Public: the literal the QMS scaffold files carry in every cell the author
# still has to fill. A clause file that still contains it is never content-bearing.
SCAFFOLD_PLACEHOLDER = "_fill in_"

# Public: the shipped template `qms generate --scaffold` renders per clause.
QMS_SCAFFOLD_TEMPLATE = (
    Path(__file__).resolve().parent
    / "templates"
    / "recommend"
    / "qms"
    / "clause_scaffold.md"
)

_MIN_BODY_WORDS = 8


@dataclass(frozen=True)
class _ContentSpec:
    """Content test for a ref: ALL patterns must match somewhere in the file text.

    ``body_only`` evaluates the patterns and the 8-word minimum on the body
    (markdown headings, blank lines and the QMS scaffold's own prompt lines
    removed); ``forbid_scaffold`` makes any remaining ``SCAFFOLD_PLACEHOLDER`` disqualify the file.
    """

    patterns: tuple[re.Pattern[str], ...]
    found_label: str
    lacks_label: str
    noun: str
    body_only: bool = False
    forbid_scaffold: bool = False
    note: str = ""  # appended to the rationale


# Raw-text marker of a signed-log line (never JSON-parsed here).
_CHAIN_LINE = r'"prev_hash"\s*:\s*"sha256:'

# Art. 17(1)(a)-(m) clause keywords. source: heuristic (no legal source);
# confidence: low; needs_founder_review: true (E-15). One case-insensitive
# pattern per clause; the founder may want different words. (h) and (i) also
# accept a signed-log line so the root incident log is content-bearing for both.
_QMS_CLAUSE_KEYWORDS: dict[str, str] = {
    "a": r"compliance|conformity|regulat",
    "b": r"design",
    "c": r"quality\s+(control|assurance)|\bQA\b|\bQC\b|development",
    "d": r"test|validat|examination",
    "e": r"specification|standard",
    "f": r"data\s+(management|governance|quality|collection)|training\s+data",
    "g": r"risk",
    "h": r"post[\s-]*market|monitor|" + _CHAIN_LINE,
    "i": r"incident|" + _CHAIN_LINE,
    "j": r"authorit|regulator|communicat",
    "k": r"record|log|retain|retention",
    "l": r"resource|supply|staff|budget",
    "m": r"accountab|responsib|owner",
}

# Minimal content markers for refs where bare file existence is not enough to
# count as content-bearing evidence.
_CONTENT_MARKERS: dict[str, _ContentSpec] = {
    "risk_register": _ContentSpec(
        patterns=(
            re.compile(
                r"risk[\s_-]*(identification|analysis|assessment)|identified\s+risks|hazard",
                re.I,
            ),
            re.compile(r"mitigat|control\s+measure|treatment|residual\s+risk", re.I),
        ),
        found_label="risk identification + mitigation",
        lacks_label="risk-identification and mitigation",
        noun="risk register",
    ),
    # Heuristic keywords for Art. 13(3) topics. source: heuristic (no legal
    # source); confidence: low; needs_founder_review: true (E-15).
    "deployer_instructions": _ContentSpec(
        patterns=(
            re.compile(r"intended\s+purpose|instructions\s+for\s+use", re.I),
            re.compile(
                r"oversight|misuse|limitation|accuracy|maintenance|contact", re.I
            ),
        ),
        found_label="Art. 13(3) topic markers",
        lacks_label="Art. 13(3) topic",
        noun="set of instructions for use",
    ),
    "technical_documentation_dossier": _ContentSpec(
        patterns=(re.compile(r'"dossier_id"'), re.compile(r'"bundle_checksum"')),
        found_label="dossier_id + bundle_checksum",
        lacks_label="dossier_id and bundle_checksum",
        noun="dossier",
        note=(
            " Presence of a dossier is not a conformity assessment; "
            "Art. 11 is never reported Met by this probe."
        ),
    ),
}
for _letter, _ref, _title in QMS_17_1_CLAUSES:
    _CONTENT_MARKERS[_ref] = _ContentSpec(
        patterns=(re.compile(_QMS_CLAUSE_KEYWORDS[_letter], re.I),),
        found_label=f"clause keyword in body text, {_title}",
        lacks_label="clause-specific keyword and minimum body length",
        noun="QMS clause document",
        body_only=True,
        forbid_scaffold=True,
    )
# One plan file satisfies both the Art. 72 row and QMS clause (h).
_CONTENT_MARKERS["post_market_monitoring_plan"] = _CONTENT_MARKERS[
    "provider_qms_17_1_h"
]
_CONTENT_MARKERS["serious_incident_log"] = _ContentSpec(
    patterns=(re.compile(_CHAIN_LINE),),
    found_label="a signed-log entry",
    lacks_label="signed-log entry",
    noun="incident log",
)


@dataclass
class ProbeResult:
    found_paths: list[str]
    code_hits: int = 0
    content_markers_met: bool | None = None
    scaffold_hits: int = 0


_SKIP_DIRS = frozenset({".venv", "node_modules", ".git"})


def _walk_files(repo_root: Path) -> list[str]:
    """Sorted repo-relative POSIX file paths; vendor dirs pruned, symlinks not followed."""
    out: list[str] = []
    for dirpath, dirs, files in os.walk(repo_root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        rel_dir = os.path.relpath(dirpath, repo_root).replace(os.sep, "/")
        for name in sorted(files):
            rel = name if rel_dir == "." else f"{rel_dir}/{name}"
            if len(rel) <= 240:
                out.append(rel)
    return sorted(out)


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Glob to case-insensitive regex (use with fullmatch).

    ``**/`` = zero or more directories, trailing ``/**`` = any file below,
    ``*`` = any run without ``/``, ``?`` = one non-``/`` char. No bracket classes.
    """
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern[i:] == "/**":
            out.append("/.+")
            i += 3
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out), re.IGNORECASE)


def _match_patterns(repo_root: Path, patterns: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    if not repo_root.is_dir():
        return found
    files: list[str] | None = None
    for pattern in patterns:
        if "*" not in pattern and "/" not in pattern:
            if (repo_root / pattern).is_file() and pattern not in found:
                found.append(pattern)
        else:
            if files is None:
                files = _walk_files(repo_root)
            rx = _glob_to_regex(pattern)
            for rel in files:
                if rx.fullmatch(rel) and rel not in found:
                    found.append(rel)
                    if len(found) >= 5:
                        return found
        if len(found) >= 5:
            return found
    return found


def _scan_code_hints(repo_root: Path, pattern: re.Pattern[str]) -> int:
    hits = 0
    for rel in _walk_files(repo_root):
        if not rel.endswith(".py"):
            continue
        path = repo_root / rel
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


def _norm_line(line: str) -> str:
    return " ".join(line.split())


# The scaffold's own review-flag comment, intro and prompt lines: never author
# content. Ceiling: only the current template wording is known; if it changes,
# keep the retired prompt lines in this set so older scaffolds still read Unfilled.
@functools.cache
def _scaffold_lines() -> frozenset[str]:
    return frozenset(
        _norm_line(ln)
        for ln in QMS_SCAFFOLD_TEMPLATE.read_text(encoding="utf-8").splitlines()
        if ln.strip()
        and not ln.lstrip().startswith("#")
        and ln.strip() != SCAFFOLD_PLACEHOLDER
    )


def _body_text(text: str) -> str:
    return "\n".join(
        ln
        for ln in text.splitlines()
        if ln.strip()
        and not ln.lstrip().startswith("#")
        and _norm_line(ln) not in _scaffold_lines()
    )


def _content_markers_met(
    repo_root: Path, found_paths: list[str], ref: str
) -> tuple[bool | None, int]:
    """(met, scaffold_hits); met is None when the ref has no content spec."""
    spec = _CONTENT_MARKERS.get(ref)
    if spec is None:
        return None, 0
    met = False
    scaffold_hits = 0
    for rel in found_paths:
        candidate = repo_root / rel
        try:
            if not candidate.is_file() or candidate.stat().st_size > 1_048_576:
                continue
            # For .json files we also just search the raw text — no parsing.
            text = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if spec.forbid_scaffold and SCAFFOLD_PLACEHOLDER in text:
            scaffold_hits += text.count(SCAFFOLD_PLACEHOLDER)
            continue
        if spec.body_only:
            text = _body_text(text)
            if len(text.split()) < _MIN_BODY_WORDS:
                continue
        if all(marker.search(text) for marker in spec.patterns):
            met = True
    return met, scaffold_hits


def run_artifact_probe(ref: str, repo_root: Path | None) -> ProbeResult:
    patterns = _PROBE_PATTERNS.get(ref, ())
    if repo_root is None or not patterns:
        return ProbeResult(found_paths=[])
    paths = _match_patterns(repo_root, patterns)
    code_hits = 0
    hint = _CODE_HINTS.get(ref)
    if hint is not None:
        code_hits = _scan_code_hints(repo_root, hint)
    met, scaffold_hits = _content_markers_met(repo_root, paths, ref)
    return ProbeResult(
        found_paths=paths,
        code_hits=code_hits,
        content_markers_met=met,
        scaffold_hits=scaffold_hits,
    )


def _probe_row(
    ref: str, repo_root: Path | None, result: ProbeResult | None = None
) -> ArticleGapStatus:
    """Map a probe ref to an honest gap row (reuses ``result`` when given)."""
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
    if result is None:
        result = run_artifact_probe(ref, repo_root)
    spec = _CONTENT_MARKERS.get(ref)
    if result.found_paths or result.code_hits:
        evidence = result.found_paths[0] if result.found_paths else f"code_hint:{ref}"
        if result.content_markers_met is True and spec is not None:
            return ArticleGapStatus(
                article="",
                status=GapStatus.PARTIAL,
                source=ArticleGapSource.ARTIFACT,
                evidence_ref=evidence,
                rationale=(
                    f"Found candidate artifact/signal for '{ref}' "
                    f"({len(result.found_paths)} path(s), {result.code_hits} code hint(s)) "
                    f"with content markers found ({spec.found_label}). "
                    "Heuristic only — not a full obligation assessment." + spec.note
                ),
                confidence=0.6,
                confidence_label=ConfidenceLabel.HEURISTIC_ESTIMATE,
            )
        if result.content_markers_met is False and spec is not None:
            if result.scaffold_hits:
                rationale = (
                    f"Found '{evidence}' but it still contains {result.scaffold_hits} "
                    f"unfilled scaffold placeholder(s) ('{SCAFFOLD_PLACEHOLDER}') — "
                    f"a scaffold is not a filled {spec.noun}."
                )
            else:
                rationale = (
                    f"Found '{evidence}' but it lacks {spec.lacks_label} "
                    f"content markers — a bare or empty file is not a {spec.noun}."
                    + spec.note
                )
            return ArticleGapStatus(
                article="",
                status=GapStatus.PARTIAL,
                source=ArticleGapSource.ARTIFACT,
                evidence_ref=evidence,
                rationale=rationale,
                confidence=0.35,
                confidence_label=ConfidenceLabel.HEURISTIC_ESTIMATE,
            )
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


class QmsCounts(NamedTuple):
    present: int
    unfilled: int
    missing: int
    unverified: int


@dataclass(frozen=True)
class QmsClauseResult:
    letter: str
    ref: str
    title: str
    row: ArticleGapStatus
    content_bearing: bool | None

    @property
    def label(self) -> str:
        if self.row.status == GapStatus.UNVERIFIED:
            return "Unverified"
        if self.row.status == GapStatus.MISSING:
            return "Missing"
        if self.row.status == GapStatus.MET:
            return "Present"
        return "Present" if self.content_bearing is not False else "Unfilled"


def qms_clause_results(repo_root: Path | None) -> list[QmsClauseResult]:
    """Per-clause Art. 17(1)(a)-(m) results, in clause order.

    The single source for every consumer (gaps fold, recommend, qms generate):
    one probe run per clause, same honesty rules as every artifact row
    (Partial/Missing/Unverified, never a fabricated Met).
    """
    out = []
    for letter, ref, title in QMS_17_1_CLAUSES:
        result = None if repo_root is None else run_artifact_probe(ref, repo_root)
        row = _probe_row(ref, repo_root, result).model_copy(
            update={"article": f"Art. 17(1)({letter})"}
        )
        met = None if result is None else result.content_markers_met
        out.append(QmsClauseResult(letter, ref, title, row, met))
    return out


def summarise_qms_clauses(results: list[QmsClauseResult]) -> QmsCounts:
    labels = [r.label for r in results]
    return QmsCounts(
        present=labels.count("Present"),
        unfilled=labels.count("Unfilled"),
        missing=labels.count("Missing"),
        unverified=labels.count("Unverified"),
    )


def qms_summary_text(counts: QmsCounts, unverified_hint: str = "") -> str:
    """ "P present / M missing" plus unfilled/unverified segments only when non-zero."""
    text = f"{counts.present} present / {counts.missing} missing"
    if counts.unfilled:
        text += f" / {counts.unfilled} unfilled"
    if counts.unverified:
        text += f" / {counts.unverified} unverified{unverified_hint}"
    return text


def artifact_gap_status(ref: str, repo_root: Path | None) -> ArticleGapStatus:
    """Map a probe ref to an honest gap row.

    For ``provider_qms`` the per-clause results are folded in when at least one
    clause file exists; the status is never MET.
    """
    row = _probe_row(ref, repo_root)
    if ref != "provider_qms" or repo_root is None:
        return row
    results = qms_clause_results(repo_root)
    found = [r for r in results if r.row.status != GapStatus.MISSING]
    if not found:
        return row
    c = summarise_qms_clauses(results)
    update: dict[str, object] = {
        "rationale": (
            f"{row.rationale} Per-clause: {c.present} present / "
            f"{c.unfilled} unfilled / {c.missing} missing (of 13)."
        )
    }
    if row.status == GapStatus.MISSING:
        update["status"] = GapStatus.PARTIAL
        update["evidence_ref"] = found[0].row.evidence_ref
    return row.model_copy(update=update)


def qms_article_17_clause_statuses(
    repo_root: Path | None,
) -> list[ArticleGapStatus]:
    """Per-clause Art. 17(1)(a)-(m) gap rows, in clause order."""
    return [r.row for r in qms_clause_results(repo_root)]
