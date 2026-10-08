"""Render an Annex IV dossier to Markdown and PDF (presentation only).

The renderer is a pure function of the dossier: it never reads the clock,
adds no compliance content and changes no dossier field. Provider placeholders
and missing items are marked ``NOT PROVIDED`` so nothing is hidden, and an
incomplete dossier says so in a banner on the first page.

Markdown and PDF share one block list (`_blocks`) so they cannot diverge.
Sections are walked by ``model_fields``, so fields added to a section model
later appear without a change here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from opencomplai_core.dossier import PROVIDER_SUPPLIED_PLACEHOLDER, AnnexIVDossier
from opencomplai_core.dossier_generator import STUB_TEXT

NOT_PROVIDED = "NOT PROVIDED"
INCOMPLETE_BANNER = (
    "INCOMPLETE: this dossier is not a complete Annex IV technical documentation file."
)
_NO_GAP = (
    "No completeness gap flagged by the dossier "
    "(schema valid, section2_complete and annex_iv_complete true)."
)
_NOT_ATTESTED = "Sections not attested by the provider are marked NOT PROVIDED below."

# Block kinds: h1 h2 banner p li li2 missing note.
Block = tuple[str, str]

_SECTION_TITLES = (
    "Section 1: General description of the AI system",
    "Section 2: Elements and development process",
    "Section 3: Monitoring, functioning and control",
    "Section 4: Performance metrics",
    "Section 5: Risk management system",
    "Section 6: Relevant changes through the lifecycle",
    "Section 7: Harmonised standards and other solutions",
    "Section 8: EU declaration of conformity",
    "Section 9: Post-market monitoring plan",
)
_PROVIDER_SECTIONS = (3, 4, 6, 7, 8, 9)


def _text(value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, Enum):
        value = value.value
    return " ".join(str(value).split())


def _is_missing(value: Any) -> bool:
    if value is None or value in ("", [], {}):
        return True
    return isinstance(value, str) and value in (
        PROVIDER_SUPPLIED_PLACEHOLDER,
        STUB_TEXT,
    )


def _emit(
    label: str, value: Any, out: list[Block], *, force_missing: bool = False
) -> None:
    if force_missing or _is_missing(value):
        out.append(("missing", label))
        if isinstance(value, str) and value:
            out.append(("note", f"placeholder text: {_text(value)}"))
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            _emit(f"{label}.{name}", getattr(value, name), out)
    elif isinstance(value, dict):
        out.append(("li", f"{label}:"))
        out.extend(("li2", f"{k}: {_text(value[k])}") for k in sorted(value, key=str))
    elif isinstance(value, list):
        if any(isinstance(v, (BaseModel, dict, list)) for v in value):
            for i, item in enumerate(value, 1):
                _emit(f"{label}[{i}]", item, out)
        else:
            out.append(("li", f"{label}:"))
            out.extend(("li2", _text(v)) for v in value)
    else:
        out.append(("li", f"{label}: {_text(value)}"))


def _banner(dossier: AnnexIVDossier, schema_valid: bool) -> list[Block]:
    unattested = [
        n
        for n in _PROVIDER_SECTIONS
        if not getattr(dossier, f"section{n}").provider_supplied
    ]
    reasons: list[str] = []
    if not schema_valid:
        reasons.append("Schema validation failed.")
    if not dossier.section2_complete:
        reasons.append("Section 2 is a stub.")
    if not dossier.annex_iv_complete:
        reasons.append("annex_iv_complete is false.")
    if reasons:
        reasons.extend(
            f"Section {n} is not provided by the provider." for n in unattested
        )
        return [("banner", INCOMPLETE_BANNER), *(("li", r) for r in reasons)]
    out: list[Block] = [("p", _NO_GAP)]
    if unattested:
        out.append(("p", _NOT_ATTESTED))
    return out


def _blocks(dossier: AnnexIVDossier, schema_valid: bool) -> list[Block]:
    out: list[Block] = [
        ("h1", f"Annex IV technical documentation dossier {dossier.dossier_id}"),
        *_banner(dossier, schema_valid),
        ("h2", "Dossier details"),
    ]
    for name in (
        "dossier_id",
        "system_id",
        "commit_ref",
        "generated_at",
        "compliance_target",
        "assessed_against",
        "rule_version",
        "bundle_checksum",
    ):
        _emit(name, getattr(dossier, name), out)
    for n, title in enumerate(_SECTION_TITLES, 1):
        section = getattr(dossier, f"section{n}")
        out.append(("h2", title))
        unattested = getattr(section, "provider_supplied", True) is False
        for name, info in type(section).model_fields.items():
            # An attestation field of an unattested section is never presented
            # as content, whatever text it carries.
            force = unattested and info.default == PROVIDER_SUPPLIED_PLACEHOLDER
            _emit(name, getattr(section, name), out, force_missing=force)
    out.append(("h2", "Article 12 record keeping"))
    if dossier.record_keeping is None:
        out.append(("p", NOT_PROVIDED))
    else:
        _emit("record_keeping", dossier.record_keeping, out)
    out.append(("h2", "Evidence hashes"))
    _emit("evidence_hashes", dossier.evidence_hashes, out)
    out.append(("h2", "Signature status"))
    out.append(("p", _text(dossier.signature_status)))
    out.append(("h2", "Scope disclaimer"))
    out.append(("p", _text(dossier.scope_disclaimer)))
    return out


_LIST_KINDS = {"li", "li2", "missing", "note"}


def render_markdown(dossier: AnnexIVDossier, *, schema_valid: bool) -> str:
    """Render the dossier as Markdown (LF, byte-stable for a fixed dossier)."""
    lines: list[str] = []
    prev = ""
    for kind, text in _blocks(dossier, schema_valid):
        if lines and not (kind in _LIST_KINDS and prev in _LIST_KINDS):
            lines.append("")
        lines.append(
            {
                "h1": f"# {text}",
                "h2": f"## {text}",
                "banner": f"**{text}**",
                "li": f"- {text}",
                "li2": f"  - {text}",
                "missing": f"- {text}: **{NOT_PROVIDED}**",
                "note": f"  - _{text}_",
            }.get(kind, text)
        )
        prev = kind
    return "\n".join(lines) + "\n"


def render_pdf(dossier: AnnexIVDossier, *, schema_valid: bool) -> bytes:
    """Render the dossier to PDF bytes using fpdf2 (same blocks as Markdown)."""
    try:
        from fpdf import FPDF
    except ImportError as exc:
        msg = "PDF export requires the optional 'reports' dependency (fpdf2>=2.7)"
        raise ImportError(msg) from exc

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    # fpdf2 stamps the current time by default; pin it to the dossier's own.
    try:
        pdf.set_creation_date(datetime.fromisoformat(dossier.generated_at))
    except ValueError:
        pdf.set_creation_date(datetime(1970, 1, 1, tzinfo=UTC))
    pdf.add_page()

    for kind, text in _blocks(dossier, schema_valid):
        shown = {
            "li": f"- {text}",
            "li2": f"    - {text}",
            "missing": f"- {text}: {NOT_PROVIDED}",
            "note": f"    ({text})",
        }.get(kind, text)
        safe = shown.encode("latin-1", errors="replace").decode("latin-1")
        bold = kind in ("h1", "h2", "banner", "missing")
        size = {"h1": 14, "h2": 12}.get(kind, 11)
        pdf.set_font("Helvetica", style="B" if bold else "", size=size)
        pdf.multi_cell(0, 6, safe)
        pdf.ln(1 if kind in _LIST_KINDS else 2)
    return bytes(pdf.output())


def write_renders(
    dossier: AnnexIVDossier,
    out_dir: Path,
    kinds: list[str],
    *,
    schema_valid: bool,
) -> list[Path]:
    """Write ``dossier_<id>.md`` and/or ``.pdf`` into *out_dir*; return the paths.

    Markdown is written before the PDF, so a missing fpdf2 (``ImportError``)
    still leaves the Markdown on disk.
    """
    written: list[Path] = []
    if "md" in kinds:
        path = out_dir / f"dossier_{dossier.dossier_id}.md"
        path.write_bytes(
            render_markdown(dossier, schema_valid=schema_valid).encode("utf-8")
        )
        written.append(path)
    if "pdf" in kinds:
        path = out_dir / f"dossier_{dossier.dossier_id}.pdf"
        path.write_bytes(render_pdf(dossier, schema_valid=schema_valid))
        written.append(path)
    return written
