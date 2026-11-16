"""Fill-in impact assessment drafts, pre-filled from the system manifest.

Two kinds: `ai-system` (one section per row of the ISO_IEC_42005 pack, read at
run time) and `dpia` (GDPR Art. 35(7)(a) to (d), own wording). Every cell the
manifest cannot fill is the text `_fill in_`; every section has an Owner cell
that stays `_fill in_`. Nothing is written into a pack directory.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from opencomplai_core.frameworks import FRAMEWORKS, pack_requirements
from opencomplai_core.models import SystemManifest

KINDS: tuple[str, ...] = ("ai-system", "dpia")
FILL_IN = "_fill in_"
DISCLAIMER = "Draft for review. Not legal advice and not an assessment by itself."
_PACK_ID = "ISO_IEC_42005"

# ponytail: keyword match on the section title, not a semantic mapping.
PREFILL: dict[str, tuple[str, ...]] = {
    "purpose": ("intended_purpose",),
    "data": ("training_data_description", "input_data_specifications"),
    "risk": ("known_limitations", "foreseeable_misuse"),
    "misuse": ("known_limitations", "foreseeable_misuse"),
    "oversight": ("human_oversight_measures",),
    "measure": ("human_oversight_measures",),
    "monitor": ("monitoring_approach",),
    "incident": ("incident_response_procedure",),
}

_DPIA_HEADER = (
    "Controller",
    "Processors",
    "Data protection officer",
    "Prior consultation (Art. 36)",
)

_DPIA_SECTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "Art. 35(7)(a)",
        "Processing and its purpose",
        "Describe what personal data is processed, how, and why.",
    ),
    (
        "Art. 35(7)(b)",
        "Necessity and proportionality",
        "Explain why the processing is needed for the purpose and why a "
        "lighter option would not do.",
    ),
    (
        "Art. 35(7)(c)",
        "Risks to the people concerned",
        "List the risks to the rights and freedoms of the people whose data "
        "is processed.",
    ),
    (
        "Art. 35(7)(d)",
        "Measures that address the risks",
        "State the safeguards and controls that answer each risk above.",
    ),
)


class AssessmentSection(BaseModel):
    ref: str
    title: str
    guidance: str
    assessment: str = FILL_IN
    source: str = "not_captured"
    populated: bool = False
    owner: str = FILL_IN


class AssessmentDocument(BaseModel):
    kind: str
    system_id: str
    generated_at: str
    header: dict[str, str] = Field(default_factory=dict)
    sections: list[AssessmentSection] = Field(default_factory=list)
    disclaimer: str = DISCLAIMER


def _text(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v).strip() for v in value if str(v).strip())
    return str(value).strip() if value else ""


def _prefill(title: str, manifest: SystemManifest) -> tuple[str, str, bool]:
    lowered = title.lower()
    fields: list[str] = []
    for keyword, names in PREFILL.items():
        if keyword in lowered:
            fields.extend(n for n in names if n not in fields)
    parts: list[str] = []
    used: list[str] = []
    for name in fields:
        text = _text(getattr(manifest, name, None))
        if text:
            parts.append(f"{name}: {text}")
            used.append(f"manifest.{name}")
    if not parts:
        return FILL_IN, "not_captured", False
    return " | ".join(parts), ", ".join(used), True


def _section(
    ref: str, title: str, guidance: str, manifest: SystemManifest
) -> AssessmentSection:
    assessment, source, populated = _prefill(title, manifest)
    return AssessmentSection(
        ref=ref,
        title=title,
        guidance=guidance,
        assessment=assessment,
        source=source,
        populated=populated,
    )


def _pack_sections(manifest: SystemManifest) -> list[AssessmentSection]:
    rows = pack_requirements(FRAMEWORKS[_PACK_ID]) or {}
    return [
        _section(row_id, str(row.get("title", "")), str(row.get("note", "")), manifest)
        for row_id, row in rows.items()
    ]


def build_assessment(
    kind: str, manifest: SystemManifest, *, generated_at: str
) -> AssessmentDocument:
    """Build the draft for `kind`; raises ValueError for an unknown kind."""
    if kind == "ai-system":
        header = {"System": manifest.system_id}
        sections = _pack_sections(manifest)
    elif kind == "dpia":
        header = dict.fromkeys(_DPIA_HEADER, FILL_IN)
        sections = [_section(r, t, g, manifest) for r, t, g in _DPIA_SECTIONS]
    else:
        raise ValueError(f"unknown kind {kind!r}; use one of: {', '.join(KINDS)}")
    return AssessmentDocument(
        kind=kind,
        system_id=manifest.system_id,
        generated_at=generated_at,
        header=header,
        sections=sections,
    )


def render_assessment_markdown(document: AssessmentDocument) -> str:
    title = {"ai-system": "AI system impact assessment", "dpia": "DPIA"}.get(
        document.kind, document.kind
    )
    lines = [
        DISCLAIMER,
        "",
        f"# {title}: {document.system_id}",
        "",
        f"Generated at: {document.generated_at}",
        "",
    ]
    for key, value in document.header.items():
        lines.append(f"- **{key}:** {value}")
    if document.header:
        lines.append("")
    for section in document.sections:
        lines += [
            f"## {section.ref} {section.title}",
            "",
            f"_{section.guidance}_" if section.guidance else "",
            "",
            f"**Assessment:** {section.assessment}",
            "",
            f"**Owner:** {section.owner}",
            "",
        ]
    return "\n".join(lines).rstrip("\n") + "\n"
