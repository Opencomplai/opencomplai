"""Render a combined scan + eval + manifest + gap-report HTML/PDF document
(opencomplai report).

Read-only rendering of already-local artifacts — no network access, no interaction
with signing/evidence/the egress proxy. Does not replace the Annex IV dossier
(`opencomplai docs generate`) and is not a second CI gate: the exit-code contract
stays exclusively with `opencomplai check`.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from opencomplai_core import __version__ as _CORE_VERSION
from opencomplai_core.models import (
    EvalSummary,
    GapReport,
    RiskResult,
    ScanSummary,
    ScanStatusArtifact,
    SystemManifest,
)
from opencomplai_core.output_envelope import wrap_scan_output

_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "report" / "report.html"

_STATUS_CLASS = {
    "met": "status-met",
    "missing": "status-missing",
    "partial": "status-partial",
    "unverified": "status-unverified",
}


def _esc(value: object) -> str:
    return html.escape(str(value))


def _render_rule_results_table(risk_result: RiskResult | None) -> str:
    if risk_result is None:
        return "<p><em>No rule-engine result supplied.</em></p>"
    rows = "\n".join(
        f"<tr><td>{_esc(r.rule_name)}</td>"
        f"<td class=\"{'status-met' if r.passed else 'status-missing'}\">"
        f"{'PASS' if r.passed else 'FAIL'}</td>"
        f"<td>{_esc(r.reference)}</td>"
        f"<td>{_esc(r.rationale)}</td></tr>"
        for r in risk_result.rule_results
    )
    return (
        "<table><tr><th>Rule</th><th>Status</th><th>Reference</th><th>Rationale</th></tr>"
        f"{rows}</table>"
    )


def _render_gap_report_table(gap_report: GapReport | None) -> str:
    if gap_report is None:
        return "<p><em>No gap report supplied — run <code>opencomplai gaps</code> first.</em></p>"
    rows = "\n".join(
        f"<tr><td>{_esc(row.article)}</td>"
        f"<td class=\"{_STATUS_CLASS[row.status.value]}\">{_esc(row.status.value.upper())}</td>"
        f"<td>{_esc(row.source.value)}</td>"
        f"<td>{_esc(row.evidence_ref)}</td>"
        f"<td>{_esc(row.rationale)}</td></tr>"
        for row in gap_report.articles
    )
    return (
        '<table id="gap-table"><thead><tr><th>Article</th><th>Status</th><th>Source</th>'
        f"<th>Evidence</th><th>Rationale</th></tr></thead><tbody>{rows}</tbody></table>"
    )


def _render_eval_summary_block(eval_summary: EvalSummary | None) -> str:
    if eval_summary is None:
        return "<p><em>No eval summary supplied — run with <code>--sample-set</code>.</em></p>"
    failed = ", ".join(eval_summary.failed_evaluator_ids) or "none"
    skipped = ", ".join(eval_summary.skipped_evaluators) or "none"
    return (
        "<table>"
        f"<tr><th>Overall outcome</th><td>{_esc(eval_summary.overall_outcome.value)}</td></tr>"
        f"<tr><th>Eval set</th><td>{_esc(eval_summary.eval_set_id)} "
        f"v{_esc(eval_summary.eval_set_version)}</td></tr>"
        f"<tr><th>Failed evaluators</th><td>{_esc(failed)}</td></tr>"
        f"<tr><th>Skipped evaluators</th><td>{_esc(skipped)}</td></tr>"
        "</table>"
    )


def _render_scan_summary_block(scan_summary: ScanSummary | None) -> str:
    if scan_summary is None:
        return "<p><em>No scan summary supplied — run with <code>--scan</code>.</em></p>"
    categories = ", ".join(scan_summary.detected_categories) or "none"
    discrepancies = ", ".join(scan_summary.discrepancies) or "none"
    return (
        "<table>"
        f"<tr><th>Severity</th><td>{_esc(scan_summary.severity.value)}</td></tr>"
        f"<tr><th>Detected categories</th><td>{_esc(categories)}</td></tr>"
        f"<tr><th>Discrepancies</th><td>{_esc(discrepancies)}</td></tr>"
        "</table>"
    )


def render_report(
    manifest: SystemManifest,
    *,
    artifact: ScanStatusArtifact | None = None,
    gap_report: GapReport | None = None,
    risk_result: RiskResult | None = None,
    eval_summary: EvalSummary | None = None,
    scan_summary: ScanSummary | None = None,
    fmt: str = "html",
) -> bytes | str:
    """Render a combined report. `fmt` is "html" or "pdf".

    `gap_report`/`eval_summary`/`scan_summary` default to whatever is embedded on
    `artifact` when not passed explicitly, so a single `compliance-artifact.json`
    (optionally produced with `check --with-gaps --scan`) is sufficient input.
    """
    if artifact is not None:
        gap_report = gap_report or artifact.gap_report
        eval_summary = eval_summary or artifact.eval_summary
        scan_summary = scan_summary or artifact.scan_summary

    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    envelope_payload = {
        "system_id": manifest.system_id,
        "commit_ref": manifest.commit_ref,
        "gap_report": json.loads(gap_report.model_dump_json()) if gap_report else None,
        "eval_summary": json.loads(eval_summary.model_dump_json()) if eval_summary else None,
        "scan_summary": json.loads(scan_summary.model_dump_json()) if scan_summary else None,
    }
    envelope = wrap_scan_output(envelope_payload, tool_version=_CORE_VERSION)
    envelope_json = html.escape(envelope.model_dump_json(), quote=False)

    replacements = {
        "{{system_id}}": _esc(manifest.system_id),
        "{{commit_ref}}": _esc(manifest.commit_ref),
        "{{generated_at}}": _esc(gap_report.generated_at if gap_report else "n/a"),
        "{{intended_purpose}}": _esc(manifest.intended_purpose),
        "{{compliance_target}}": _esc(manifest.compliance_target),
        "{{high_risk_presumption}}": _esc(manifest.high_risk_presumption),
        "{{rule_results_table}}": _render_rule_results_table(risk_result),
        "{{gap_report_table}}": _render_gap_report_table(gap_report),
        "{{eval_summary_block}}": _render_eval_summary_block(eval_summary),
        "{{scan_summary_block}}": _render_scan_summary_block(scan_summary),
        "{{envelope_json}}": envelope_json,
    }
    html_doc = template
    for placeholder, value in replacements.items():
        html_doc = html_doc.replace(placeholder, value)

    if fmt == "html":
        return html_doc

    if fmt == "pdf":
        try:
            from fpdf import FPDF
        except ImportError as exc:
            msg = "PDF export requires the optional 'reports' dependency (fpdf2>=2.7)"
            raise ImportError(msg) from exc

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)

        def write_line(text: str) -> None:
            safe = text.encode("latin-1", errors="replace").decode("latin-1")
            pdf.multi_cell(0, 6, safe)
            pdf.ln(2)

        write_line(f"Opencomplai Compliance Report - {manifest.system_id}")
        write_line(f"Commit: {manifest.commit_ref}")
        write_line(f"Intended purpose: {manifest.intended_purpose}")
        if gap_report is not None:
            write_line("Gap report:")
            for row in gap_report.articles:
                write_line(
                    f"{row.article}: {row.status.value.upper()} "
                    f"({row.source.value}: {row.evidence_ref})"
                )
        return bytes(pdf.output())

    msg = f"Unsupported report format: {fmt!r} (expected 'html' or 'pdf')"
    raise ValueError(msg)
