"""Art. 17(1)(a)-(m) QMS document builder (`opencomplai qms generate`, CP-15).

Renders a filled quality-management-system document from CP-7's own
per-clause artifact probes (`gap_probes.qms_article_17_clause_statuses`) --
reused directly, never re-derived, so this command can never disagree with
what `opencomplai recommend`/`opencomplai gaps` already report for the same
repo (same rule CP-14's `fria generate` follows for the Art. 27 obligation).

Kept in its own module rather than folded into `gap_probes.py` /
`recommend_engine.py` / `models.py` so this new command's plumbing doesn't
share an edit surface with sibling Phase-3 generators landing in the same
batch (`fria generate`, the NIST AI RMF evaluated target).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from opencomplai_core.gap_probes import QMS_17_1_CLAUSES, qms_article_17_clause_statuses
from opencomplai_core.models import GapStatus

# Same wording as `recommend_engine`'s qms_outline.md Status column, so a
# clause reads identically whether seen via `recommend` or `qms generate`.
# MET is included for completeness even though today's artifact probes never
# return it (heuristic-only, never fabricate Met -- see gap_probes.py).
_STATUS_LABEL: dict[GapStatus, str] = {
    GapStatus.MET: "Present",
    GapStatus.PARTIAL: "Present",
    GapStatus.MISSING: "Missing",
    GapStatus.UNVERIFIED: "Unverified",
}


@dataclass(frozen=True)
class QmsClauseEntry:
    letter: str
    title: str
    status: GapStatus  # raw probe status: met/partial/missing/unverified
    status_label: str  # display label: Present/Missing/Unverified
    evidence_ref: str
    rationale: str


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


def build_qms_document(
    repo_root: Path | None,
    system_id: str = "",
    commit_ref: str = "HEAD",
    generated_at: str = "",
    evidence_hashes: list[str] | None = None,
) -> QmsDocument:
    """Build the Art. 17(1)(a)-(m) document from CP-7's own per-clause probes.

    `repo_root=None` yields 13 honest UNVERIFIED rows (no probe run) rather
    than a fabricated verdict -- matches
    `qms_article_17_clause_statuses(None)`'s own contract.
    """
    rows = qms_article_17_clause_statuses(repo_root)
    clauses = [
        QmsClauseEntry(
            letter=letter,
            title=title,
            status=row.status,
            status_label=_STATUS_LABEL[row.status],
            evidence_ref=row.evidence_ref,
            rationale=row.rationale,
        )
        for (letter, _ref, title), row in zip(QMS_17_1_CLAUSES, rows, strict=True)
    ]
    present = sum(1 for c in clauses if c.status in (GapStatus.MET, GapStatus.PARTIAL))
    missing = sum(1 for c in clauses if c.status == GapStatus.MISSING)
    unverified = sum(1 for c in clauses if c.status == GapStatus.UNVERIFIED)
    return QmsDocument(
        system_id=system_id,
        commit_ref=commit_ref,
        generated_at=generated_at,
        clauses=clauses,
        present_count=present,
        missing_count=missing,
        unverified_count=unverified,
        evidence_hashes=list(evidence_hashes or []),
    )


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
        'Art. 17 -- "Present" means a matching file/path was found (heuristic, '
        'not a legal determination), "Missing" means none was, "Unverified" '
        "means the probe did not run. This is a starting point for triage, not "
        "a substitute for review.",
        "",
        "| # | QMS element (Art. 17(1)) | Evidence status | Raw status | "
        "Evidence reference | Rationale |",
        "|---|---|---|---|---|---|",
    ]
    for clause in doc.clauses:
        rationale = (clause.rationale or "(no rationale recorded)").replace("\n", " ")
        lines.append(
            f"| ({clause.letter}) | {clause.title} | {clause.status_label} | "
            f"{clause.status.value} | `{clause.evidence_ref}` | {rationale} |"
        )
    summary = f"{doc.present_count} present / {doc.missing_count} missing"
    if doc.unverified_count:
        summary += f" / {doc.unverified_count} unverified"
    lines += [
        "",
        f"**Summary:** {summary} (of 13 clauses).",
        "",
        "## Evidence references",
        "",
    ]
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
