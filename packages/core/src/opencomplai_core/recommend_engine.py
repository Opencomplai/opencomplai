"""Render copy-paste remediation templates from a GapReport (opencomplai recommend).

Supports Markdown stubs and compile-checked Python examples. No code execution at
render time. Every output cites the article/gap row that triggered it.
"""

from __future__ import annotations

import json
import shutil
from functools import lru_cache
from pathlib import Path

from opencomplai_core.gap_probes import QMS_17_1_CLAUSES, qms_article_17_clause_statuses
from opencomplai_core.models import ArticleGapStatus, GapReport, GapStatus

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "recommend"

_ACTIONABLE_STATUSES = frozenset({GapStatus.MISSING, GapStatus.PARTIAL})

# Labels for the qms_outline.md per-clause Status column — mirrors the
# Met/Partial/Missing/Unverified honesty model, worded for a human reading a
# single QMS clause row ("present" reads better than "partial" out of context).
_QMS_CLAUSE_LABEL: dict[GapStatus, str] = {
    GapStatus.MET: "Present",
    GapStatus.PARTIAL: "Present",
    GapStatus.MISSING: "Missing",
    GapStatus.UNVERIFIED: "Unverified",
}


_FRIA_ASSESSMENT_LETTERS: tuple[str, ...] = ("a", "b", "c", "d", "e", "f")

_FRIA_PREFILLED_NOTICE = (
    "Fill in each cell with the actual assessment content for this deployment. "
    "No claims below are pre-filled — an empty or unfilled table is not evidence "
    "of a completed FRIA."
)


def _render_fria_fill_in(content: str) -> str:
    """Fill fria_template.md's Art. 27(1)(a)-(f) assessment placeholders.

    `opencomplai recommend` has no manifest/checker context to draw on here
    (only a GapReport + repo_root), so it keeps the template's pre-CP-14
    fill-in-only contract: every cell reads `_fill in_`, never a fabricated
    claim. `opencomplai fria generate` (opencomplai_core.fria) is the real
    consumer that fills these same placeholders with actual manifest/checker
    data — see that module for the data-populated path.
    """
    content = content.replace("{{fria_prefilled_notice}}", _FRIA_PREFILLED_NOTICE)
    for letter in _FRIA_ASSESSMENT_LETTERS:
        content = content.replace(f"{{{{fria_1{letter}_assessment}}}}", "_fill in_")
    return content


def _render_qms_clause_table(content: str, repo_root: Path | None) -> str:
    """Fill the qms_outline.md per-clause {{qms_17_1_<letter>_status}} cells."""
    rows = qms_article_17_clause_statuses(repo_root)
    present = sum(1 for r in rows if r.status in (GapStatus.MET, GapStatus.PARTIAL))
    missing = sum(1 for r in rows if r.status == GapStatus.MISSING)
    unverified = sum(1 for r in rows if r.status == GapStatus.UNVERIFIED)
    for (letter, _ref, _title), row in zip(QMS_17_1_CLAUSES, rows, strict=True):
        content = content.replace(
            f"{{{{qms_17_1_{letter}_status}}}}", _QMS_CLAUSE_LABEL[row.status]
        )
    summary = f"{present} present / {missing} missing"
    if unverified:
        summary += f" / {unverified} unverified (pass --repo-root to evaluate)"
    return content.replace("{{qms_17_1_summary}}", summary)


@lru_cache(maxsize=1)
def load_template_map() -> dict[str, dict[str, str]]:
    path = _TEMPLATES_DIR / "template_map.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _render(content: str, row: ArticleGapStatus, template_id: str) -> str:
    return (
        content.replace("{{article}}", row.article)
        .replace("{{status}}", row.status.value.upper())
        .replace("{{source}}", row.source.value)
        .replace("{{evidence_ref}}", row.evidence_ref)
        .replace("{{rationale}}", row.rationale or "(no rationale recorded)")
        .replace("{{template_id}}", template_id)
    )


def render_recommendations(
    gap_report: GapReport, output_dir: Path, repo_root: Path | None = None
) -> list[Path]:
    """Write one remediation template per Missing/Partial article row.

    Returns the list of files written. Python templates are copied (optionally
    with a short header comment noting the triggering article). Markdown templates
    get placeholder substitution. `repo_root`, when supplied, additionally
    populates qms_outline.md's per-clause Art. 17(1)(a)-(m) status table —
    without it those cells honestly read "Unverified" (no probe run).
    """
    template_map = load_template_map()
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for row in gap_report.articles:
        if row.status not in _ACTIONABLE_STATUSES:
            continue
        mapping = template_map.get(row.article)
        if mapping is None:
            continue

        kind = mapping.get("kind", "markdown")
        template_path = _TEMPLATES_DIR / mapping["file"]
        article_slug = row.article.lower().replace(" ", "").replace(".", "")
        template_id = mapping["template_id"]

        if kind == "python":
            suffix = template_path.suffix or ".py"
            out_path = output_dir / f"{article_slug}-{template_id}{suffix}"
            body = template_path.read_text(encoding="utf-8")
            header = (
                f"# Triggered by {row.article} status={row.status.value} "
                f"source={row.source.value} evidence={row.evidence_ref}\n"
            )
            if not body.lstrip().startswith("# Triggered by"):
                body = header + body
            out_path.write_text(body, encoding="utf-8")
            written.append(out_path)
            for asset in mapping.get("assets", []) or []:
                asset_src = _TEMPLATES_DIR / asset
                if asset_src.is_file():
                    dest = output_dir / Path(asset).name
                    shutil.copy2(asset_src, dest)
                    written.append(dest)
        else:
            content = template_path.read_text(encoding="utf-8")
            rendered = _render(content, row, template_id)
            if template_id == "qms_outline":
                rendered = _render_qms_clause_table(rendered, repo_root)
            elif template_id == "fria_template":
                rendered = _render_fria_fill_in(rendered)
            out_path = output_dir / f"{article_slug}-{template_id}.md"
            out_path.write_text(rendered, encoding="utf-8")
            written.append(out_path)

    return written
