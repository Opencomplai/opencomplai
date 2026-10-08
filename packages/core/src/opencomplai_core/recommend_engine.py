"""Render copy-paste remediation templates from a GapReport (opencomplai recommend).

Supports Markdown stubs and compile-checked Python examples. No code execution at
render time. Every output cites the article/gap row that triggered it.
"""

from __future__ import annotations

import json
import re
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Any

from opencomplai_core.backlog import SortOrder, sort_rows
from opencomplai_core.control_catalog import get_catalog
from opencomplai_core.frameworks import EU_AI_ACT, framework_of
from opencomplai_core.gap_probes import (
    qms_clause_results,
    qms_summary_text,
    summarise_qms_clauses,
)
from opencomplai_core.gpai_training_pack import (
    get_gpai_training_pack,
    render_training_summary_markdown,
)
from opencomplai_core.models import ArticleGapStatus, GapReport, GapStatus

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates" / "recommend"

_ACTIONABLE_STATUSES = frozenset({GapStatus.MISSING, GapStatus.PARTIAL})

# Rows of other frameworks with no template of their own get this one.
_GENERIC_MAPPING = {
    "template_id": "generic_requirement",
    "kind": "markdown",
    "file": "generic_requirement.md",
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
    results = qms_clause_results(repo_root)
    for r in results:
        content = content.replace(f"{{{{qms_17_1_{r.letter}_status}}}}", r.label)
    summary = qms_summary_text(
        summarise_qms_clauses(results), " (pass --repo-root to evaluate)"
    )
    return content.replace("{{qms_17_1_summary}}", summary)


@lru_cache(maxsize=1)
def load_template_map() -> dict[str, dict[str, Any]]:
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
    gap_report: GapReport,
    output_dir: Path,
    repo_root: Path | None = None,
    sort: SortOrder = SortOrder.article,
) -> list[Path]:
    """Write one remediation template per Missing/Partial article row.

    EU AI Act rows without a template_map.json entry are skipped; rows of
    other frameworks ("<FW>:<id>") fall back to generic_requirement.md.

    A markdown entry may carry an `also` list of further markdown mappings; each
    is written next to the main file for the same row.

    Returns the list of files written. Python templates are copied (optionally
    with a short header comment noting the triggering article). Markdown templates
    get placeholder substitution. `repo_root`, when supplied, additionally
    populates qms_outline.md's per-clause Art. 17(1)(a)-(m) status table —
    without it those cells honestly read "Unverified" (no probe run).
    """
    template_map = load_template_map()
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for row in sort_rows(gap_report.articles, sort):
        if row.status not in _ACTIONABLE_STATUSES:
            continue
        framework = framework_of(row.article)
        mapping = template_map.get(row.article)
        if mapping is None:
            if framework == EU_AI_ACT:
                continue
            mapping = _GENERIC_MAPPING

        kind = mapping.get("kind", "markdown")
        template_path = _TEMPLATES_DIR / mapping["file"]
        # "Art. 9" -> "art9", "FIXTURE:REQ-1" -> "fixture--req-1".
        article_slug = re.sub(
            r"[^a-z0-9_-]", "", row.article.lower().replace(":", "--")
        )
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
            elif template_id == "generic_requirement":
                entry = get_catalog().get(row.article)
                rendered = rendered.replace("{{framework}}", framework).replace(
                    "{{title}}", entry.title if entry is not None else row.article
                )
            out_path = output_dir / f"{article_slug}-{template_id}.md"
            out_path.write_text(rendered, encoding="utf-8")
            written.append(out_path)
            for extra in mapping.get("also", []) or []:
                extra_text = (_TEMPLATES_DIR / extra["file"]).read_text(
                    encoding="utf-8"
                )
                extra_out = _render(extra_text, row, extra["template_id"])
                if extra["template_id"] == "gpai_training_summary":
                    extra_out = extra_out.replace(
                        "{{gpai_training_summary}}",
                        render_training_summary_markdown(get_gpai_training_pack()),
                    )
                extra_path = output_dir / f"{article_slug}-{extra['template_id']}.md"
                extra_path.write_text(extra_out, encoding="utf-8")
                written.append(extra_path)

    return written
