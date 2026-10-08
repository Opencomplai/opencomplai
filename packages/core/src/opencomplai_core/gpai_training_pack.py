"""GPAI provider pack extras: training-content summary and Code of Practice map.

Loads and validates `data/gpai_training_pack.json`, mirroring
`harmonised_standards.get_catalog()`'s fail-loud convention: a missing or
malformed file raises `ValueError` and never yields an empty or partial pack.

Every row is low confidence and `needs_founder_review=true`: the content is a
recollection that has not been checked against the primary texts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).resolve().parent / "data" / "gpai_training_pack.json"

_CONFIDENCES = {"low", "medium"}
_COMMON_KEYS = ("id", "title", "source", "source_url", "confidence")
_SECTION_KEYS = ("prompt", "article_ref")
_CHAPTER_KEYS = ("article_refs", "maps_to", "applies_to", "status_note")
_LIST_KEYS = ("article_refs", "maps_to")
_LISTS = {
    "training_summary_sections": _SECTION_KEYS,
    "code_of_practice_chapters": _CHAPTER_KEYS,
}


@dataclass(frozen=True)
class TrainingSummarySection:
    id: str
    title: str
    prompt: str
    article_ref: str
    source: str
    source_url: str | None
    confidence: str
    needs_founder_review: bool


@dataclass(frozen=True)
class CopChapter:
    id: str
    title: str
    article_refs: tuple[str, ...]
    maps_to: tuple[str, ...]
    applies_to: str
    status_note: str
    source: str
    source_url: str | None
    confidence: str
    needs_founder_review: bool


@dataclass(frozen=True)
class GpaiTrainingPack:
    sections: tuple[TrainingSummarySection, ...]
    chapters: tuple[CopChapter, ...]


def _text(v: object) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _text_list(v: object) -> bool:
    return isinstance(v, list) and bool(v) and all(_text(x) for x in v)


def validate_gpai_training_pack(raw: object) -> list[str]:
    """Return one message per defect; an empty list means the pack is valid."""
    if not isinstance(raw, dict):
        return ["pack is not a JSON object"]
    errs: list[str] = []
    if not isinstance(raw.get("_meta"), dict):
        errs.append("'_meta' is missing or not an object")
    seen: set[object] = set()
    for name, extra in _LISTS.items():
        rows = raw.get(name)
        if not isinstance(rows, list) or not rows:
            errs.append(f"'{name}' is missing or empty")
            continue
        for n, row in enumerate(rows):
            if not isinstance(row, dict):
                errs.append(f"{name}[{n}] is not an object")
                continue
            rid = row.get("id")
            label = f"{name}[{rid if _text(rid) else n}]"
            if not _text(rid):
                errs.append(f"{label} has an empty or malformed id")
            elif rid in seen:
                errs.append(f"{label} has a duplicate id")
            else:
                seen.add(rid)
            for key in (*_COMMON_KEYS, *extra, "needs_founder_review"):
                if key not in row:
                    errs.append(f"{label} is missing key '{key}'")
            if "source" in row and not _text(row["source"]):
                errs.append(f"{label} has an empty source")
            url = row.get("source_url")
            if url is not None and not _text(url):
                errs.append(f"{label} has a malformed source_url")
            if "confidence" in row and row["confidence"] not in _CONFIDENCES:
                errs.append(f"{label} has invalid confidence {row['confidence']!r}")
            if "needs_founder_review" in row and (
                row["needs_founder_review"] is not True
            ):
                errs.append(f"{label} must have needs_founder_review=true")
            for key in ("title", *extra):
                if key not in row:
                    continue
                ok = _text_list(row[key]) if key in _LIST_KEYS else _text(row[key])
                if not ok:
                    errs.append(f"{label} has an empty or malformed '{key}'")
    return errs


@lru_cache(maxsize=1)
def get_gpai_training_pack() -> GpaiTrainingPack:
    """Return the validated pack; raise ValueError on any defect."""
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(
            f"gpai_training_pack: cannot read {_DATA_PATH}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"gpai_training_pack: invalid JSON in {_DATA_PATH}: {exc}"
        ) from exc
    errs = validate_gpai_training_pack(raw)
    if errs:
        raise ValueError("gpai_training_pack: invalid pack: " + "; ".join(errs))
    sections = tuple(
        TrainingSummarySection(
            **{k: r[k] for k in (*_COMMON_KEYS, *_SECTION_KEYS)},
            needs_founder_review=True,
        )
        for r in raw["training_summary_sections"]
    )
    chapters = tuple(
        CopChapter(
            **{k: r[k] for k in (*_COMMON_KEYS, "applies_to", "status_note")},
            article_refs=tuple(r["article_refs"]),
            maps_to=tuple(r["maps_to"]),
            needs_founder_review=True,
        )
        for r in raw["code_of_practice_chapters"]
    )
    return GpaiTrainingPack(sections=sections, chapters=chapters)


def render_training_summary_markdown(pack: GpaiTrainingPack) -> str:
    """Render the summary template as markdown: blank entries, no dates, no clock."""
    lines = [
        "# Summary of training content (draft template)",
        "",
        "> Draft: every section below needs founder review. Nothing here has been "
        "checked against the primary texts.",
        "",
    ]
    for s in pack.sections:
        lines += [
            f"## {s.title}",
            "",
            f"Draft, needs founder review. Reference: {s.article_ref}.",
            "",
            s.prompt,
            "",
            f"Source: {s.source}",
            f"Confidence: {s.confidence}",
            "",
            "Provider entry:",
            "",
        ]
    return "\n".join(lines)
