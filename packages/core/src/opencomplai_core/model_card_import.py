"""Offline import of a Hugging Face model card's YAML front matter.

Pure function: no file or network access. The caller reads the card and injects
``today`` (E-14).

Mapping (tool behaviour, not a compliance conclusion):

- ``datasets``                      -> ``training_data_description``
- ``base_model`` / ``library_name`` / ``pipeline_tag`` -> ``model_architecture``
- ``model-index[*].results[*].metrics[*]`` (finite int/float values)
  -> ``performance_metrics``, keyed ``"<dataset.type>/<metric.type>"``
  (or ``"<metric.type>"`` without a dataset type)

Everything else (license, tags, language, the card body) is ignored;
``known_limitations`` is not imported.

"Attested" means provider-declared, NOT verified: the values are whatever the
card says, recorded with their source so a reader can tell where they came
from. Nothing in ``check`` or ``gaps`` reads this record.

Unverified: the card layout follows Hugging Face's published model-card
metadata as the spec describes it; it was not checked against live docs.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import yaml

from opencomplai_core.models import ImportedFieldEvidence

MAX_CARD_CHARS = 262144
MAX_METRICS = 50
MAX_LIST_ITEMS = 20
MAX_STR_CHARS = 500
SOURCE = "huggingface_model_card"

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class ModelCardError(ValueError):
    """The card cannot be imported (no front matter, bad YAML, too large)."""


@dataclass(frozen=True)
class ModelCardImport:
    fields: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, ImportedFieldEvidence] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _clean(value: Any) -> str:
    return _CONTROL.sub("", str(value)).strip()[:MAX_STR_CHARS]


def _strings(value: Any) -> list[str]:
    items = value if isinstance(value, list) else [value]
    out = [_clean(v) for v in items[:MAX_LIST_ITEMS] if isinstance(v, str)]
    return [s for s in out if s]


def _front_matter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ModelCardError("model card has no YAML front matter")
    for i, line in enumerate(lines[1:], start=1):
        if line == "---":
            return "\n".join(lines[1:i])
    raise ModelCardError("model card front matter is not closed with '---'")


def _finite(v: Any) -> float | None:
    """The value as a finite float, or None (bool, non-number, inf/nan, huge int)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        f = float(v)
    except OverflowError:
        return None
    return f if math.isfinite(f) else None


def _metrics(meta: dict[str, Any], warnings: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    index = meta.get("model-index")
    for entry in index if isinstance(index, list) else []:
        results = entry.get("results") if isinstance(entry, dict) else None
        for res in results if isinstance(results, list) else []:
            if not isinstance(res, dict):
                continue
            ds = res.get("dataset")
            ds_type = _clean(ds.get("type", "")) if isinstance(ds, dict) else ""
            metrics = res.get("metrics")
            for m in metrics if isinstance(metrics, list) else []:
                if not isinstance(m, dict) or not _clean(m.get("type", "")):
                    continue
                name = _clean(m["type"])
                key = f"{ds_type}/{name}" if ds_type else name
                v = _finite(m.get("value"))
                if v is None:
                    warnings.append(
                        f"metric {key!r} dropped: value is not a finite number"
                    )
                elif key in out:
                    warnings.append(f"metric {key!r} appears twice; kept the first")
                elif len(out) >= MAX_METRICS:
                    warnings.append(
                        f"metric {key!r} dropped: more than {MAX_METRICS} metrics"
                    )
                else:
                    out[key] = v
    return out


def import_model_card(text: str, *, source_name: str, today: date) -> ModelCardImport:
    if len(text) > MAX_CARD_CHARS:
        raise ModelCardError(f"model card is larger than {MAX_CARD_CHARS} characters")
    fm = _front_matter(text)
    try:
        meta = yaml.safe_load(fm)
    except (yaml.YAMLError, RecursionError) as exc:
        raise ModelCardError(
            f"model card front matter is not valid YAML: {exc}"
        ) from exc
    if not isinstance(meta, dict):
        raise ModelCardError("model card front matter is not a mapping")

    warnings: list[str] = []
    fields: dict[str, Any] = {}

    datasets = _strings(meta.get("datasets"))
    if datasets:
        fields["training_data_description"] = (
            "Datasets declared in the model card: " + ", ".join(datasets)
        )

    parts = []
    for key, label in (
        ("base_model", "base_model"),
        ("library_name", "library"),
        ("pipeline_tag", "pipeline"),
    ):
        vals = _strings(meta.get(key)) if meta.get(key) is not None else []
        if vals:
            parts.append(f"{label}={', '.join(vals)}")
    if parts:
        fields["model_architecture"] = "Declared in the model card: " + "; ".join(parts)

    metrics = _metrics(meta, warnings)
    if metrics:
        fields["performance_metrics"] = metrics

    stamp: dict[str, Any] = {
        "source": SOURCE,
        "status": "attested",
        "source_file": re.split(r"[\\/]", source_name)[-1] or "model card",
        "card_sha256": hashlib.sha256(fm.encode("utf-8")).hexdigest(),
        "imported_on": today.isoformat(),
    }
    evidence = {k: ImportedFieldEvidence(**stamp) for k in fields}
    return ModelCardImport(fields=fields, evidence=evidence, warnings=warnings)
