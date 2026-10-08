"""Art. 17(1)(a)-(m) QMS document builder (`opencomplai qms generate`, CP-15).

Renders a filled quality-management-system document from CP-7's own
per-clause artifact probes (`gap_probes.qms_clause_results`) --
reused directly, never re-derived, so this command can never disagree with
what `opencomplai recommend`/`opencomplai gaps` already report for the same
repo (same rule CP-14's `fria generate` follows for the Art. 27 obligation).

Kept in its own module rather than folded into `gap_probes.py` /
`recommend_engine.py` / `models.py` so this new command's plumbing doesn't
share an edit surface with sibling Phase-3 generators landing in the same
batch (`fria generate`, the NIST AI RMF evaluated target).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from opencomplai_core.gap_probes import (
    QMS_17_1_CLAUSES,
    QMS_SCAFFOLD_TEMPLATE,
    QmsCounts,
    qms_clause_results,
    qms_summary_text,
    run_artifact_probe,
    summarise_qms_clauses,
)
from opencomplai_core.harmonised_standards import get_catalog as get_standards
from opencomplai_core.models import GapStatus, SystemManifest

# unverified: post-Omnibus (Reg. (EU) 2026/1744) wording of Art. 63 not checked
_MICRO_NOTE_TEXT = (
    "Art. 63 lets microenterprises satisfy some QMS elements in a simplified "
    "manner; this document keeps all 13 clauses and does not drop any. "
    "Confirm the scope of the simplification with counsel."
)
_MICRO_NOTE_SOURCE = "Regulation (EU) 2024/1689 Art. 63(1)"


@dataclass(frozen=True)
class QmsClauseEntry:
    letter: str
    title: str
    status: GapStatus  # raw probe status: met/partial/missing/unverified
    status_label: str  # display label: Present/Unfilled/Missing/Unverified
    evidence_ref: str
    rationale: str
    confidence: float | None = None
    manifest_content: str = ""  # from the manifest, never from file evidence
    manifest_source: str = ""  # manifest field names that supplied the content


@dataclass(frozen=True)
class QmsStandardEntry:
    id: str
    title: str
    status: str  # catalogue status verbatim: harmonised/published/draft
    source_url: str
    declared_in_manifest: bool | None  # None = no manifest, not checked
    needs_founder_review: bool


@dataclass(frozen=True)
class ProfileNote:
    text: str
    source: str
    confidence: str
    needs_founder_review: bool


@dataclass(frozen=True)
class QmsDocument:
    system_id: str
    commit_ref: str
    generated_at: str
    clauses: list[QmsClauseEntry]
    present_count: int
    missing_count: int
    unverified_count: int
    evidence_hashes: list[str] = field(default_factory=list)
    unfilled_count: int = 0
    standards: list[QmsStandardEntry] = field(default_factory=list)
    profile_notes: list[ProfileNote] = field(default_factory=list)
    has_manifest: bool = False


# clause letter -> manifest fields that may fill it. A manifest statement is
# shown beside the probe result; it never changes probe status or counts.
_MANIFEST_FIELDS: dict[str, tuple[str, ...]] = {
    "e": ("harmonised_standards", "alternative_solutions"),
    "h": (
        "post_market_monitoring_plan_ref",
        "post_market_monitoring_summary",
        "monitoring_approach",
    ),
    "i": ("incident_response_procedure",),
}


def _manifest_fill(manifest: SystemManifest | None, letter: str) -> tuple[str, str]:
    """(content, source field names) for one clause; empty fields add nothing."""
    parts: list[str] = []
    sources: list[str] = []
    for name in _MANIFEST_FIELDS.get(letter, ()) if manifest is not None else ():
        value = getattr(manifest, name, None)
        if isinstance(value, list):
            text = ", ".join(v.strip() for v in value if v and v.strip())
        else:
            text = (value or "").strip()
        if text:
            parts.append(text)
            sources.append(name)
    return "; ".join(parts), ", ".join(sources)


def _std_key(value: str) -> str:
    """`EN 18286`, `EN-18286` and `en18286:2026` compare equal."""
    return re.sub(r":\d{4}$", "", re.sub(r"[\s-]+", "", value).lower())


def _qms_standards(manifest: SystemManifest | None) -> list[QmsStandardEntry]:
    declared = (
        None
        if manifest is None
        else {_std_key(v) for v in manifest.harmonised_standards}
    )
    return [
        QmsStandardEntry(
            id=e.id,
            title=e.title,
            status=e.status,
            source_url=e.source_url,
            declared_in_manifest=(
                None if declared is None else _std_key(e.id) in declared
            ),
            needs_founder_review=e.needs_founder_review,
        )
        for e in get_standards().values()
        if "Art. 17" in e.articles_covered
    ]


def build_qms_document(
    repo_root: Path | None,
    system_id: str = "",
    commit_ref: str = "HEAD",
    generated_at: str = "",
    evidence_hashes: list[str] | None = None,
    manifest: SystemManifest | None = None,
) -> QmsDocument:
    """Build the Art. 17(1)(a)-(m) document from CP-7's own per-clause probes.

    `repo_root=None` yields 13 honest UNVERIFIED rows (no probe run) rather
    than a fabricated verdict -- matches
    `qms_article_17_clause_statuses(None)`'s own contract.
    """
    results = qms_clause_results(repo_root)
    fills = {r.letter: _manifest_fill(manifest, r.letter) for r in results}
    clauses = [
        QmsClauseEntry(
            letter=r.letter,
            title=r.title,
            status=r.row.status,
            status_label=r.label,
            evidence_ref=r.row.evidence_ref,
            rationale=r.row.rationale,
            confidence=r.row.confidence,
            manifest_content=fills[r.letter][0],
            manifest_source=fills[r.letter][1],
        )
        for r in results
    ]
    counts = summarise_qms_clauses(results)
    return QmsDocument(
        system_id=system_id,
        commit_ref=commit_ref,
        generated_at=generated_at,
        clauses=clauses,
        present_count=counts.present,
        missing_count=counts.missing,
        unverified_count=counts.unverified,
        evidence_hashes=list(evidence_hashes or []),
        unfilled_count=counts.unfilled,
        standards=_qms_standards(manifest),
        profile_notes=(
            [ProfileNote(_MICRO_NOTE_TEXT, _MICRO_NOTE_SOURCE, "low", True)]
            if manifest is not None and manifest.organisation_size == "micro"
            else []
        ),
        has_manifest=manifest is not None,
    )


# letter -> file stem under docs/qms/. Each stem must stay the first-pattern
# stem (`docs/qms/<stem>*`) of its clause probe in gap_probes._PROBE_PATTERNS.
QMS_SCAFFOLD_STEMS: dict[str, str] = {
    "a": "regulatory-compliance-strategy",
    "b": "design-control",
    "c": "quality-management-procedures",
    "d": "testing-validation",
    "e": "technical-documentation",
    "f": "data-governance",
    "g": "risk-management-system",
    "h": "post-market-monitoring",
    "i": "serious-incident-reporting",
    "j": "regulatory-communication",
    "k": "record-keeping",
    "l": "resource-management",
    "m": "accountability-framework",
}

_SCAFFOLD_TEMPLATE = QMS_SCAFFOLD_TEMPLATE


@dataclass(frozen=True)
class ScaffoldEntry:
    letter: str
    path: str  # repo-relative POSIX
    action: str  # "created" | "skipped"


def scaffold_qms(repo_root: Path) -> list[ScaffoldEntry]:
    """Write one starter file per Art. 17(1) clause; never overwrite anything.

    A clause is skipped when its target exists or the clause probe already
    finds a file of the user's own elsewhere. Starter files carry the
    placeholder literal, so the probes read them as Unfilled until edited.
    """
    # read_text normalises CRLF checkouts; write_bytes keeps output \n everywhere
    template = _SCAFFOLD_TEMPLATE.read_text(encoding="utf-8")
    out: list[ScaffoldEntry] = []
    for letter, ref, title in QMS_17_1_CLAUSES:
        rel = f"docs/qms/{QMS_SCAFFOLD_STEMS[letter]}.md"
        target = repo_root / rel
        if target.exists() or run_artifact_probe(ref, repo_root).found_paths:
            out.append(ScaffoldEntry(letter, rel, "skipped"))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        text = template.replace("{{letter}}", letter).replace("{{title}}", title)
        target.write_bytes(text.encode("utf-8"))
        out.append(ScaffoldEntry(letter, rel, "created"))
    return out


def render_qms_document_markdown(doc: QmsDocument) -> str:
    """Render the filled Art. 17(1)(a)-(m) QMS document as Markdown.

    Unlike `templates/recommend/qms_outline.md` (a fill-in-the-blank stub),
    every row here is fully populated from the probe results actually
    computed for this repo -- this is the "generate", not "outline", form.
    """
    lines = [
        "# Quality Management System -- Art. 17(1)(a)-(m)",
        "",
        f"**System:** {doc.system_id or '(not specified)'}  ",
        f"**Commit:** {doc.commit_ref}  ",
        f"**Generated:** {doc.generated_at or '(not recorded)'}  ",
        "",
        "Status is a convention-based artifact probe per Art. 17(1) sub-point, "
        "the same probes `opencomplai recommend`/`opencomplai gaps` use for "
        'Art. 17 -- "Present" means a matching file/path with content was found '
        '(heuristic, not a legal determination), "Unfilled" means a file was '
        'found but it is still a scaffold or has no content, "Missing" means '
        'none was, "Unverified" means the probe did not run. '
        "This is a starting point for triage, not "
        "a substitute for review.",
        "",
        "| # | QMS element (Art. 17(1)) | Evidence status | Raw status | "
        "Confidence | Evidence reference | Rationale |"
        + (" Manifest-declared |" if doc.has_manifest else ""),
        "|---|---|---|---|---|---|---|" + ("---|" if doc.has_manifest else ""),
    ]
    for clause in doc.clauses:
        rationale = (clause.rationale or "(no rationale recorded)").replace("\n", " ")
        conf = "n/a" if clause.confidence is None else f"{clause.confidence:.2f}"
        row = (
            f"| ({clause.letter}) | {clause.title} | {clause.status_label} | "
            f"{clause.status.value} | {conf} | `{clause.evidence_ref}` | {rationale} |"
        )
        if doc.has_manifest:
            declared = clause.manifest_content.replace("\n", " ").replace("|", "\\|")
            row += f" {declared} |"
        lines.append(row)
    summary = qms_summary_text(
        QmsCounts(
            doc.present_count,
            doc.unfilled_count,
            doc.missing_count,
            doc.unverified_count,
        )
    )
    lines += [
        "",
        f"**Summary:** {summary} (of 13 clauses).",
    ]
    if doc.has_manifest:
        lines += [
            "",
            "Manifest-declared text is what the system manifest states. It is "
            "not file evidence and does not change the status above.",
        ]
    lines += ["", "## Standards", ""]
    for std in doc.standards:
        declared = {True: "yes", False: "no", None: "not checked"}[
            std.declared_in_manifest
        ]
        note = (
            " (not a harmonised standard: not cited in the Official Journal)"
            if std.status != "harmonised"
            else ""
        )
        review = "; needs founder review" if std.needs_founder_review else ""
        lines += [
            f"- **{std.id}**: {std.title}. Catalogue status: `{std.status}`{note}.",
            f"  Declared in manifest: {declared}{review}. Source: {std.source_url}",
        ]
    if doc.profile_notes:
        lines += ["", "## Profile notes", ""]
        for note in doc.profile_notes:
            flag = "needs founder review" if note.needs_founder_review else "reviewed"
            lines.append(
                f"- {note.text} (source: {note.source}; "
                f"confidence: {note.confidence}; {flag})"
            )
    lines += ["", "## Evidence references", ""]
    if doc.evidence_hashes:
        lines.append(
            "SHA-256 hashes of evidence objects cited via "
            "`--scan-report`/`--eval-report`:"
        )
        lines.extend(f"- `{h}`" for h in doc.evidence_hashes)
    else:
        lines.append(
            "No evidence-vault references supplied (pass `--scan-report`/"
            "`--eval-report`, or attach evidence via "
            "`opencomplai controls attach-evidence`)."
        )
    lines.append("")
    return "\n".join(lines)
