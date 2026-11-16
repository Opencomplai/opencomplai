"""Model card generator: a Markdown card with YAML front matter from the manifest.

A pure builder plus a Markdown renderer. The front matter uses the keys the
model card importer reads (`model-index` results and metrics), so the metrics
written here read back unchanged. A section with no data in the manifest says
so; nothing is invented.

Manifest text is untrusted: control characters are stripped and a body line
that is exactly `---` is prefixed with a backslash so it cannot close the
front matter. Values listed under Provenance are provider-declared, not
verified.
"""

from __future__ import annotations

import re
from datetime import date

import yaml
from pydantic import BaseModel, Field

from opencomplai_core.models import SystemManifest

NOT_CAPTURED = "Not captured in the system manifest."
CLOSING_LINE = "Draft for review. It records what the manifest declares."

_CONTROL_KEEP_NEWLINE = re.compile(r"[\x00-\x09\x0b-\x1f\x7f-\x9f]")
_CONTROL_ALL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class ModelCardSection(BaseModel):
    key: str
    title: str
    body: str
    source: str = Field(description="Manifest field(s) the section is built from")
    populated: bool


class ModelCard(BaseModel):
    system_id: str
    commit_ref: str
    generated_on: str
    sections: list[ModelCardSection]
    metrics: dict[str, float] = Field(default_factory=dict)
    provenance: list[dict[str, str]] = Field(default_factory=list)


def _text(value: str) -> str:
    """Strip control characters (a newline stays); CR becomes a newline."""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return _CONTROL_KEEP_NEWLINE.sub("", value).strip()


def _one_line(value: str) -> str:
    return _CONTROL_ALL.sub("", value).strip()


def _bullets(items: list[str]) -> str:
    cleaned = [_text(i) for i in items]
    return "\n".join(f"- {i}" for i in cleaned if i)


def _section(key: str, title: str, source: str, body: str) -> ModelCardSection:
    body = body.strip()
    if body:
        return ModelCardSection(
            key=key, title=title, body=body, source=source, populated=True
        )
    return ModelCardSection(
        key=key, title=title, body=NOT_CAPTURED, source=source, populated=False
    )


def _clean_metrics(metrics: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, value in metrics.items():
        clean = _one_line(key)
        if clean and clean not in out:
            out[clean] = float(value)
    return out


def build_model_card(manifest: SystemManifest, *, today: date) -> ModelCard:
    metrics = _clean_metrics(manifest.performance_metrics)

    evaluation_parts: list[str] = []
    if metrics:
        evaluation_parts.append(
            "\n".join(f"- `{k}`: {v:g}" for k, v in sorted(metrics.items()))
        )
    rationale = _text(manifest.metrics_appropriateness_rationale or "")
    if rationale:
        evaluation_parts.append(f"Why these metrics: {rationale}")

    provenance: list[dict[str, str]] = []
    for name in sorted(manifest.imported_evidence):
        ev = manifest.imported_evidence[name]
        provenance.append(
            {
                "field": _one_line(name),
                "source": _one_line(ev.source),
                "status": _one_line(ev.status),
                "imported_on": _one_line(ev.imported_on),
            }
        )
    provenance_body = ""
    if provenance:
        provenance_body = (
            "\n".join(
                f"- `{p['field']}`: source {p['source']}, status {p['status']}, "
                f"imported on {p['imported_on']}"
                for p in provenance
            )
            + "\n\nThese values are provider-declared, not verified."
        )

    sections = [
        _section(
            "intended_use",
            "Intended use",
            "intended_purpose",
            _text(manifest.intended_purpose),
        ),
        _section(
            "model_details",
            "Model details",
            "model_architecture",
            _text(manifest.model_architecture or ""),
        ),
        _section(
            "training_data",
            "Training data",
            "training_data_description",
            _text(manifest.training_data_description or ""),
        ),
        _section(
            "evaluation",
            "Evaluation",
            "performance_metrics, metrics_appropriateness_rationale",
            "\n\n".join(evaluation_parts),
        ),
        _section(
            "limitations",
            "Limitations",
            "known_limitations",
            _bullets(manifest.known_limitations),
        ),
        _section(
            "foreseeable_misuse",
            "Foreseeable misuse",
            "foreseeable_misuse",
            _bullets(manifest.foreseeable_misuse),
        ),
        _section(
            "human_oversight",
            "Human oversight",
            "human_oversight_measures",
            _bullets(manifest.human_oversight_measures),
        ),
        _section(
            "monitoring",
            "Monitoring",
            "monitoring_approach",
            _text(manifest.monitoring_approach or ""),
        ),
        _section("provenance", "Provenance", "imported_evidence", provenance_body),
    ]
    return ModelCard(
        system_id=_one_line(manifest.system_id),
        commit_ref=_one_line(manifest.commit_ref),
        generated_on=today.isoformat(),
        sections=sections,
        metrics=metrics,
        provenance=provenance,
    )


def _front_matter(card: ModelCard) -> str:
    meta: dict[str, object] = {"tags": ["opencomplai"]}
    if card.metrics:
        by_dataset: dict[str, list[dict[str, object]]] = {}
        for key, value in sorted(card.metrics.items()):
            dataset, sep, metric = key.partition("/")
            if not sep:
                dataset, metric = "", key
            by_dataset.setdefault(dataset, []).append({"type": metric, "value": value})
        results: list[dict[str, object]] = []
        for dataset, metric_list in by_dataset.items():
            result: dict[str, object] = {"metrics": metric_list}
            if dataset:
                result["dataset"] = {"type": dataset, "name": dataset}
            results.append(result)
        meta["model-index"] = [{"name": card.system_id, "results": results}]
    return yaml.safe_dump(meta, sort_keys=True, allow_unicode=True)


def _guard(body: str) -> str:
    return "\n".join("\\---" if line == "---" else line for line in body.split("\n"))


def render_model_card_markdown(card: ModelCard) -> str:
    out = ["---", _front_matter(card).rstrip("\n"), "---", ""]
    out.append(f"# Model card: {card.system_id}")
    out.append("")
    out.append(f"Commit: {card.commit_ref}. Generated on {card.generated_on}.")
    out.append("")
    for section in card.sections:
        out.append(f"## {section.title}")
        out.append("")
        out.append(_guard(section.body))
        out.append("")
    out.append(CLOSING_LINE)
    return "\n".join(out) + "\n"
