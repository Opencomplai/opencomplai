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
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from opencomplai_core.models import (
    ArticleGapSource,
    ArticleGapStatus,
    ConfidenceLabel,
    GapStatus,
)
from opencomplai_core.probe_registry import (
    ProbeDef,
    flags_to_int,
    flags_to_letters,
    iter_probe_files,
    parse_probe_file,
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
    # Provenance-only evaluator ref: upper case with no patterns, which the
    # shared-file format does not take, so it stays here.
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
_PROBE_PATTERNS: dict[str, tuple[str, ...]] = {}

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

_CODE_HINTS: dict[str, re.Pattern[str]] = {}

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

# Public: the Art. 72 plan template `recommend` renders; its own lines are scaffold too.
PMM_PLAN_TEMPLATE = (
    Path(__file__).resolve().parent
    / "templates"
    / "recommend"
    / "post_market_monitoring_plan.md"
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
    # The markers choose the files: only matched files that satisfy them count as
    # found (the first five globbed files would otherwise hide a later hit). For
    # probes that read code, where most matched files are not evidence.
    select: bool = False


_CONTENT_MARKERS: dict[str, _ContentSpec] = {}


@dataclass(frozen=True)
class _ClauseDocument:
    """A clause-document probe: one document, one section per clause."""

    noun: str
    # clause id -> (title, marker regexes); every marker has to match the section.
    clauses: dict[str, tuple[str, tuple[re.Pattern[str], ...]]]


# Filled by _register_probe_files(); keyed by probe ref.
_CLAUSE_DOCUMENTS: dict[str, _ClauseDocument] = {}

# The probe definitions live in probes/eu_ai_act.json and probes/ai_security.json,
# read by _register_probe_files(). Notes that sat on the literals:
# - provenance entries marked heuristic: no legal source, low confidence, needs
#   founder review (E-15); the Art. 17(1)(a)-(m) clause words are one
#   case-insensitive pattern per clause, (h) and (i) also accept a signed-log line;
# - the raw-text marker of a signed-log line is never JSON-parsed here;
# - one plan file satisfies both the Art. 72 row and QMS clause (h);
# - the ISO/IEC 27090 attack terms mirror the pack's threat headings, with
#   "evasion" and "backdoor" needing a second word;
# - library names are matched where used (import, directive), never as bare words;
# - supply-chain pins: SBOM header, hash written as a key, or a hub revision
#   pinned to a commit hash.


def _register_probe_files(
    files: Iterable[tuple[Path, str | None]] | None = None,
) -> None:
    """Add the probes declared in JSON files to the four tables.

    A ref that is already registered is an error, never an override. The
    default source is every shared and pack-local file."""
    for path, prefix in iter_probe_files() if files is None else files:
        parsed = parse_probe_file(path, prefix)
        for ref in parsed:
            if (
                ref in _PROBE_PATTERNS
                or ref in _CONTENT_MARKERS
                or ref in _CODE_HINTS
                or ref in PROBE_PROVENANCE
                or ref in _CLAUSE_DOCUMENTS
            ):
                raise ValueError(f"{path}: probe ref {ref!r} is already registered")
        for probe in parsed.values():
            _add_probe(probe)


def _add_probe(probe: ProbeDef) -> None:
    _PROBE_PATTERNS[probe.ref] = probe.patterns
    if probe.markers is not None:
        m = probe.markers
        _CONTENT_MARKERS[probe.ref] = _ContentSpec(
            patterns=tuple(re.compile(p, flags_to_int(f)) for p, f in m["all"]),
            found_label=m["found_label"],
            lacks_label=m["lacks_label"],
            noun=m["noun"],
            body_only=m["body_only"],
            forbid_scaffold=m["forbid_scaffold"],
            note=m["note"],
            select=m["select"],
        )
    if probe.code_hint is not None:
        pattern, flags = probe.code_hint
        _CODE_HINTS[probe.ref] = re.compile(pattern, flags_to_int(flags))
    if probe.provenance is not None:
        PROBE_PROVENANCE[probe.ref] = dict(probe.provenance)
    if probe.clauses is not None:
        _CLAUSE_DOCUMENTS[probe.ref] = _ClauseDocument(
            noun=probe.noun or "",
            clauses={
                clause: (
                    body["title"],
                    tuple(re.compile(p, flags_to_int(f)) for p, f in body["markers"]),
                )
                for clause, body in probe.clauses.items()
            },
        )


_register_probe_files()


def registry_snapshot() -> dict:
    """Every registered ref with its patterns, marker regexes as
    [pattern, flags], the other content-spec fields, code hint and provenance."""
    refs = (
        set(_PROBE_PATTERNS)
        | set(_CONTENT_MARKERS)
        | set(_CODE_HINTS)
        | set(PROBE_PROVENANCE)
        | set(_CLAUSE_DOCUMENTS)
    )
    out: dict[str, dict] = {}
    for ref in sorted(refs):
        spec = _CONTENT_MARKERS.get(ref)
        hint = _CODE_HINTS.get(ref)
        provenance = PROBE_PROVENANCE.get(ref)
        out[ref] = {
            "patterns": list(_PROBE_PATTERNS.get(ref, ())),
            "markers": None
            if spec is None
            else {
                "all": [[p.pattern, flags_to_letters(p.flags)] for p in spec.patterns],
                "found_label": spec.found_label,
                "lacks_label": spec.lacks_label,
                "noun": spec.noun,
                "body_only": spec.body_only,
                "forbid_scaffold": spec.forbid_scaffold,
                "select": spec.select,
                "note": spec.note,
            },
            "code_hint": None
            if hint is None
            else [hint.pattern, flags_to_letters(hint.flags)],
            "provenance": None if provenance is None else dict(provenance),
        }
        doc = _CLAUSE_DOCUMENTS.get(ref)
        if doc is not None:
            out[ref]["type"] = "clause_document"
            out[ref]["noun"] = doc.noun
            out[ref]["clauses"] = {
                clause: {
                    "title": title,
                    "markers": [[p.pattern, flags_to_letters(p.flags)] for p in pats],
                }
                for clause, (title, pats) in doc.clauses.items()
            }
    return out


# Never selected from: a Python environment's installed packages (its name varies).
_VENDORED_DIR = "site-packages"


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


def _match_patterns(
    repo_root: Path, patterns: tuple[str, ...], select: _ContentSpec | None = None
) -> list[str]:
    """Up to five repo-relative paths matching ``patterns``; with ``select``, only
    those whose content satisfies it (and not under a ``site-packages`` dir)."""
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
                    if select is not None and (
                        _VENDORED_DIR in rel.split("/")
                        or not _spec_met(select, repo_root / rel)[0]
                    ):
                        continue
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
def _strip_marker(line: str) -> str:
    return _norm_line(line.replace(SCAFFOLD_PLACEHOLDER, ""))


def _template_lines(path: Path) -> list[str]:
    return [
        ln
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


@functools.cache
def _scaffold_lines() -> frozenset[str]:
    return frozenset(
        _strip_marker(ln)
        for ln in _template_lines(QMS_SCAFFOLD_TEMPLATE)
        if ln.strip() != SCAFFOLD_PLACEHOLDER
    )


# Plan-template lines carry {{variables}}; each becomes a fullmatch pattern over
# its literal pieces. Lines with under 8 literal characters are too generic to match.
@functools.cache
def _scaffold_line_regexes() -> tuple[re.Pattern[str], ...]:
    out = []
    for ln in _template_lines(PMM_PLAN_TEMPLATE):
        pieces = re.split(r"\{\{[^}]*\}\}", _strip_marker(ln))
        if sum(len(p) for p in pieces) >= 8:
            out.append(re.compile(".*".join(re.escape(p) for p in pieces)))
    return tuple(out)


def _is_label_only(line: str) -> bool:
    s = re.sub(r"^(?:[-*+>]|\d+[.)])\s*", "", line.strip()).rstrip("*_` ")
    return s.endswith(":")


def _is_scaffold_line(line: str) -> bool:
    norm = _strip_marker(line)
    return (
        norm in _scaffold_lines()
        or any(r.fullmatch(norm) for r in _scaffold_line_regexes())
        or _is_label_only(norm)
    )


def _body_text(text: str) -> str:
    return "\n".join(
        ln
        for ln in text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("#") and not _is_scaffold_line(ln)
    )


def _spec_met(spec: _ContentSpec, candidate: Path) -> tuple[bool, int]:
    """(markers hold, scaffold placeholders seen) for one file."""
    try:
        if not candidate.is_file() or candidate.stat().st_size > 1_048_576:
            return False, 0
        # For .json files we also just search the raw text — no parsing.
        text = candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False, 0
    if spec.forbid_scaffold and SCAFFOLD_PLACEHOLDER in text:
        return False, text.count(SCAFFOLD_PLACEHOLDER)
    if spec.body_only:
        text = _body_text(text)
        if len(text.split()) < _MIN_BODY_WORDS:
            return False, 0
    return all(marker.search(text) for marker in spec.patterns), 0


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
        ok, scaffold = _spec_met(spec, repo_root / rel)
        met = met or ok
        scaffold_hits += scaffold
    return met, scaffold_hits


_CLAUSE_ANCHOR = re.compile(r"^[ \t]*<!--\s*clause:\s*(.*?)\s*-->[ \t]*$")


def split_clause_ref(ref: str) -> tuple[str, str | None]:
    """(probe ref, clause id or None) of ``<ref>`` or ``<ref>#<clause>``.

    A ``#`` on a ref that is not a clause document, or a clause the document
    does not declare, raises ValueError."""
    base, sep, clause = ref.partition("#")
    if not sep:
        return ref, None
    doc = _CLAUSE_DOCUMENTS.get(base)
    if doc is None:
        raise ValueError(f"probe {base!r} is not a clause document: {ref!r}")
    if clause not in doc.clauses:
        raise ValueError(f"probe {base!r} has no clause {clause!r}")
    return base, clause


def probe_exists(ref: str) -> bool:
    """True for a registered ref, and for ``<ref>#<clause>`` of a declared clause."""
    try:
        base, _ = split_clause_ref(ref)
    except ValueError:
        return False
    return (
        base in _PROBE_PATTERNS
        or base in _CONTENT_MARKERS
        or base in _CODE_HINTS
        or base in PROBE_PROVENANCE
        or base in _CLAUSE_DOCUMENTS
    )


@dataclass(frozen=True)
class ClauseResult:
    clause: str
    title: str
    state: str  # present | unfilled | missing | unverified
    row: ArticleGapStatus


def _clause_sections(text: str) -> dict[str, str]:
    """Clause id -> section text (anchor line excluded); the first anchor of a
    clause wins."""
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        m = _CLAUSE_ANCHOR.match(line)
        if m:
            clause = m.group(1)
            if clause in sections:
                current = None
            else:
                current = sections[clause] = []
            continue
        if current is not None:
            current.append(line)
    return {clause: "\n".join(lines) for clause, lines in sections.items()}


def _clause_state(
    doc: _ClauseDocument, clause: str, sections: dict[str, str]
) -> tuple[str, int]:
    """(state, scaffold placeholders seen) of one clause."""
    section = sections.get(clause)
    if section is None:
        return "missing", 0
    placeholders = section.count(SCAFFOLD_PLACEHOLDER)
    if placeholders:
        return "unfilled", placeholders
    if len(_body_text(section).split()) < _MIN_BODY_WORDS:
        return "unfilled", 0
    if all(marker.search(section) for marker in doc.clauses[clause][1]):
        return "present", 0
    return "unfilled", 0


def _clause_document_path(ref: str, repo_root: Path) -> str | None:
    paths = _match_patterns(repo_root, _PROBE_PATTERNS.get(ref, ()))
    return sorted(paths)[0] if paths else None


def _read_document(repo_root: Path, rel: str) -> str:
    try:
        candidate = repo_root / rel
        if candidate.stat().st_size > 1_048_576:
            return ""
        return candidate.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _unverified_row(ref: str) -> ArticleGapStatus:
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


def _missing_row(ref: str) -> ArticleGapStatus:
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


def _clause_row(
    ref: str, clause: str, state: str, path: str, placeholders: int
) -> ArticleGapStatus:
    doc = _CLAUSE_DOCUMENTS[ref]
    if state == "present":
        rationale = (
            f"Found '{path}' with clause '{clause}' holding content markers "
            f"({doc.clauses[clause][0]}). "
            "Heuristic only — not a full obligation assessment."
        )
        confidence = 0.6
    elif state == "unfilled":
        if placeholders:
            rationale = (
                f"Found '{path}' but clause '{clause}' still contains "
                f"{placeholders} unfilled scaffold placeholder(s) "
                f"('{SCAFFOLD_PLACEHOLDER}') — a scaffold is not a filled {doc.noun}."
            )
        else:
            rationale = (
                f"Found '{path}' but clause '{clause}' lacks content markers "
                f"or body text — a bare or empty section is not a {doc.noun}."
            )
        confidence = 0.35
    else:
        rationale = (
            f"Found '{path}' but it has no section for clause '{clause}' "
            f"(expected a '<!-- clause: {clause} -->' line)."
        )
        confidence = 0.35
    return ArticleGapStatus(
        article="",
        status=GapStatus.PARTIAL,
        source=ArticleGapSource.ARTIFACT,
        evidence_ref=path,
        rationale=rationale,
        confidence=confidence,
        confidence_label=ConfidenceLabel.HEURISTIC_ESTIMATE,
    )


def _clause_row_for(
    ref: str, clause: str, repo_root: Path | None
) -> tuple[ArticleGapStatus, str]:
    """(row, state) of one ``<ref>#<clause>``."""
    full = f"{ref}#{clause}"
    if repo_root is None:
        return _unverified_row(full), "unverified"
    rel = _clause_document_path(ref, repo_root)
    if rel is None:
        return _missing_row(full), "missing"
    sections = _clause_sections(_read_document(repo_root, rel))
    state, placeholders = _clause_state(_CLAUSE_DOCUMENTS[ref], clause, sections)
    return _clause_row(ref, clause, state, rel, placeholders), state


def clause_document_results(ref: str, repo_root: Path | None) -> list[ClauseResult]:
    """One result per clause of a clause-document probe, in declared order."""
    doc = _CLAUSE_DOCUMENTS.get(ref)
    if doc is None:
        raise ValueError(f"probe {ref!r} is not a clause document")
    out = []
    for clause, (title, _) in doc.clauses.items():
        row, state = _clause_row_for(ref, clause, repo_root)
        out.append(ClauseResult(clause, title, state, row))
    return out


def _bare_clause_row(ref: str, repo_root: Path | None) -> ArticleGapStatus:
    if repo_root is None:
        return _unverified_row(ref)
    rel = _clause_document_path(ref, repo_root)
    if rel is None:
        return _missing_row(ref)
    doc = _CLAUSE_DOCUMENTS[ref]
    sections = _clause_sections(_read_document(repo_root, rel))
    states = [_clause_state(doc, c, sections)[0] for c in doc.clauses]
    present = states.count("present")
    return ArticleGapStatus(
        article="",
        status=GapStatus.PARTIAL,
        source=ArticleGapSource.ARTIFACT,
        evidence_ref=rel,
        rationale=(
            f"Found candidate artifact '{rel}' for '{ref}'. "
            "Heuristic only — not a full obligation assessment. "
            f"Per-clause: {present} present / {states.count('unfilled')} unfilled / "
            f"{states.count('missing')} missing (of {len(states)})."
        ),
        confidence=0.6 if present else 0.35,
        confidence_label=ConfidenceLabel.HEURISTIC_ESTIMATE,
    )


def run_artifact_probe(ref: str, repo_root: Path | None) -> ProbeResult:
    base, clause = split_clause_ref(ref)
    if base in _CLAUSE_DOCUMENTS:
        rel = None if repo_root is None else _clause_document_path(base, repo_root)
        if repo_root is None or rel is None:
            return ProbeResult(found_paths=[])
        if clause is None:
            return ProbeResult(found_paths=[rel])
        sections = _clause_sections(_read_document(repo_root, rel))
        state, placeholders = _clause_state(_CLAUSE_DOCUMENTS[base], clause, sections)
        return ProbeResult(
            found_paths=[rel],
            content_markers_met=state == "present",
            scaffold_hits=placeholders,
        )
    patterns = _PROBE_PATTERNS.get(ref, ())
    if repo_root is None or not patterns:
        return ProbeResult(found_paths=[])
    spec = _CONTENT_MARKERS.get(ref)
    paths = _match_patterns(
        repo_root, patterns, spec if spec is not None and spec.select else None
    )
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
    base, clause = split_clause_ref(ref)
    if base in _CLAUSE_DOCUMENTS:
        if clause is None:
            return _bare_clause_row(ref, repo_root)
        return _clause_row_for(base, clause, repo_root)[0]
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


def supporting_gap_status(ref: str, repo_root: Path | None) -> ArticleGapStatus | None:
    """The probe's row for a ``"role": "supporting"`` source, or None.

    None unless the probe found evidence: a matched path (or code hint) whose
    content markers, if the ref has any, hold. A supporting source that finds
    nothing, or only an empty or off-topic file, must change nothing; `build_gap_report`
    applies the row.
    """
    base, clause = split_clause_ref(ref)
    if repo_root is None:
        return None
    result = run_artifact_probe(ref, repo_root)
    if base in _CLAUSE_DOCUMENTS:
        if not result.found_paths:
            return None
        if clause is not None and not result.content_markers_met:
            return None
        return _probe_row(ref, repo_root, result)
    if not (result.found_paths or result.code_hits):
        return None
    if result.content_markers_met is False:
        return None
    return _probe_row(ref, repo_root, result)


def corroboration_status(
    ref: str, repo_root: Path | None
) -> tuple[ArticleGapStatus, bool] | None:
    """The probe's row for a ``"role": "corroborating"`` artifact source.

    Returns ``(row, evidenced)``; `evidenced` is true when the content markers
    hold. None without a repo root (the probe did not run). `ref` may be
    ``<ref>#<clause>``. `build_gap_report` composes the row with an attestation.
    """
    if repo_root is None:
        return None
    result = run_artifact_probe(ref, repo_root)
    row = _probe_row(ref, repo_root, result)
    return row, result.content_markers_met is True


def qms_article_17_clause_statuses(
    repo_root: Path | None,
) -> list[ArticleGapStatus]:
    """Per-clause Art. 17(1)(a)-(m) gap rows, in clause order."""
    return [r.row for r in qms_clause_results(repo_root)]
