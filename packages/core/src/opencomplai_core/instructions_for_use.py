"""Art. 13(3) instructions-for-use generator.

Renders an instructions-for-use pack from the system manifest, one row per
Art. 13(3) point. Same honesty rule as `fria.py`: a point with no data in the
manifest is listed as "not captured", never fabricated.

Every point's text and legal reference is the planner's reading of Regulation
(EU) 2024/1689 Art. 13(3), not checked against the primary text, so each one
ships `confidence: medium` and `needs_founder_review: true` (E-15). The clock is
injected (E-14): nothing here reads the current time.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from pydantic import BaseModel, Field

from opencomplai_core.models import SystemManifest

IFU_DISCLAIMER = (
    "Informational draft only, not legal advice. Every point and legal reference "
    "below is flagged for founder review and has not been checked against the "
    "primary text of Art. 13(3)."
)

_NOT_CAPTURED = (
    "Not captured by the system manifest: the provider must supply this before "
    "the instructions for use can be considered complete."
)

_LEGAL = "Regulation (EU) 2024/1689 Art. 13(3)"


@dataclass(frozen=True)
class IFUPointDef:
    point: str
    element: str
    legal_ref: str
    confidence: str = "medium"
    needs_founder_review: bool = True


def _p(point: str, ref: str, element: str) -> IFUPointDef:
    return IFUPointDef(point, element, f"{_LEGAL}{ref}")


IFU_POINTS: tuple[IFUPointDef, ...] = (
    _p("a", "(a)", "Identity and contact details of the provider"),
    _p("b_i", "(b)(i)", "Intended purpose"),
    _p(
        "b_ii",
        "(b)(ii)",
        "Level of accuracy, robustness and cybersecurity against which the system was tested",
    ),
    _p("b_limits", "(b)(ii)", "Known limitations"),
    _p(
        "b_iii",
        "(b)(iii)",
        "Known or foreseeable circumstances, including misuse, that may lead to risk",
    ),
    _p(
        "b_iv",
        "(b)(iv)",
        "Technical capabilities and characteristics to provide information relevant to explain its output",
    ),
    _p(
        "b_v",
        "(b)(v)",
        "Performance regarding specific persons or groups of persons",
    ),
    _p("b_vi", "(b)(vi)", "Specifications for the input data"),
    _p(
        "b_vii",
        "(b)(vii)",
        "Information to enable deployers to interpret the output and use it appropriately",
    ),
    _p(
        "c",
        "(c)",
        "Changes to the system pre-determined at the initial conformity assessment",
    ),
    _p("d", "(d)", "Human oversight measures"),
    _p("e", "(e)", "Expected lifetime and necessary maintenance and care measures"),
    _p("f", "(f)", "Mechanisms to collect, store and interpret the logs"),
)


class IFUPoint(BaseModel):
    """One row of the Art. 13(3) instructions-for-use outline."""

    point: str
    element: str
    legal_ref: str
    content: str
    source: str = Field(..., description="Manifest field path, or 'not_captured'")
    populated: bool
    confidence: str
    needs_founder_review: bool


class IFUDocument(BaseModel):
    instructions_id: str = Field(
        ..., description="Deterministic uuid5 of system and commit"
    )
    system_id: str
    commit_ref: str
    generated_at: str = Field(..., description="Injected ISO 8601 timestamp")
    points: list[IFUPoint]
    populated_point_count: int
    total_points: int
    not_captured_points: list[str]
    disclaimer: str = IFU_DISCLAIMER


def _text(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def _bullets(items: list[str]) -> str | None:
    kept = [i.strip() for i in items if i and i.strip()]
    return "; ".join(kept) if kept else None


def _metrics(m: SystemManifest) -> tuple[str | None, str]:
    parts: list[str] = []
    sources: list[str] = []
    if m.performance_metrics:
        parts.append(", ".join(f"{k}={v}" for k, v in m.performance_metrics.items()))
        sources.append("manifest.performance_metrics")
    if rationale := _text(m.metrics_appropriateness_rationale):
        parts.append(f"Rationale: {rationale}")
        sources.append("manifest.metrics_appropriateness_rationale")
    return ("; ".join(parts) or None, " + ".join(sources))


def _resolve(point: str, m: SystemManifest) -> tuple[str | None, str]:
    """(content or None when not captured, source field path)."""
    if point == "b_ii":
        return _metrics(m)
    simple: dict[str, tuple[str | None, str]] = {
        "a": (_text(m.provider_contact), "manifest.provider_contact"),
        "b_i": (_text(m.intended_purpose), "manifest.intended_purpose"),
        "b_limits": (_bullets(m.known_limitations), "manifest.known_limitations"),
        "b_iii": (_bullets(m.foreseeable_misuse), "manifest.foreseeable_misuse"),
        "b_vi": (
            _text(m.input_data_specifications),
            "manifest.input_data_specifications",
        ),
        "c": (_bullets(m.predetermined_changes), "manifest.predetermined_changes"),
        "d": (
            _bullets(m.human_oversight_measures),
            "manifest.human_oversight_measures",
        ),
        "e": (
            _text(m.expected_lifetime_and_maintenance),
            "manifest.expected_lifetime_and_maintenance",
        ),
        "f": (_text(m.log_interpretation), "manifest.log_interpretation"),
    }
    # b_iv, b_v and b_vii have no manifest field: always not captured.
    return simple.get(point, (None, "not_captured"))


def generate_instructions_for_use(
    manifest: SystemManifest, *, generated_at: str
) -> IFUDocument:
    points: list[IFUPoint] = []
    for d in IFU_POINTS:
        content, source = _resolve(d.point, manifest)
        points.append(
            IFUPoint(
                point=d.point,
                element=d.element,
                legal_ref=d.legal_ref,
                content=content or _NOT_CAPTURED,
                source=source if content else "not_captured",
                populated=content is not None,
                confidence=d.confidence,
                needs_founder_review=d.needs_founder_review,
            )
        )
    return IFUDocument(
        instructions_id=str(
            uuid.uuid5(
                uuid.NAMESPACE_URL, f"{manifest.system_id}|{manifest.commit_ref}"
            )
        ),
        system_id=manifest.system_id,
        commit_ref=manifest.commit_ref,
        generated_at=generated_at,
        points=points,
        populated_point_count=sum(p.populated for p in points),
        total_points=len(points),
        not_captured_points=[p.point for p in points if not p.populated],
    )


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_instructions_for_use_markdown(doc: IFUDocument) -> str:
    lines = [
        f"# Instructions for use (Art. 13): {doc.system_id}",
        "",
        f"> {doc.disclaimer}",
        "",
        f"Commit: `{doc.commit_ref}`. Generated at {doc.generated_at}. "
        f"Populated {doc.populated_point_count} of {doc.total_points} points.",
        "",
        "| Art. 13(3) point | Element | Content | Source |",
        "|---|---|---|---|",
    ]
    for p in doc.points:
        flag = " (Needs review)" if p.needs_founder_review else ""
        lines.append(
            f"| {_cell(p.legal_ref)} | {_cell(p.element)} | {_cell(p.content)} "
            f"| `{p.source}`{flag} |"
        )
    lines += ["", "## Not captured", ""]
    by_id = {p.point: p for p in doc.points}
    lines += [
        f"- `{pid}`: {by_id[pid].element}" for pid in doc.not_captured_points
    ] or ["None."]
    return "\n".join(lines) + "\n"
