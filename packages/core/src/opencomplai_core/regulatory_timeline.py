"""Regulatory timeline: when each EU AI Act obligation starts to apply.

Presentation-only lookup over `data/regulatory_timeline.json`. It never feeds
the checker engine, `obligations.json` or any signed or ingested shape. Every
date is flagged for founder review; a `null` date is shown as "date
unconfirmed", never guessed. Status wording takes an injected `today` (E-14).
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import cache, lru_cache
from pathlib import Path
from typing import Literal

TIMELINE_PATH = Path(__file__).resolve().parent / "data" / "regulatory_timeline.json"

_CONFIDENCE = frozenset({"high", "medium", "low"})
_BASES = frozenset({"annex_iii", "annex_i"})
_ART = re.compile(r"Arts?\.?\s*(\d+)(?:\s*[-–—]\s*(\d+))?")  # noqa: RUF001
Status = Literal["in_force", "upcoming", "unconfirmed"]


@dataclass(frozen=True)
class TimelineEntry:
    id: str
    title: str
    applies_from: str | None
    articles: tuple[str, ...]  # gap keys, ranges already expanded
    scope_note: str
    source: str
    confidence: str
    needs_founder_review: bool
    knowledge_ref: str | None = None  # one ref, or several joined by commas
    note: str | None = None
    high_risk_basis: str | None = (
        None  # "annex_iii" or "annex_i" on the two high-risk dates
    )
    framework: str = "EU_AI_ACT"
    requirements: tuple[str, ...] = ()  # pack row ids; EU entries use `articles`
    duration: str | None = None  # free text for a deadline that is a period


def articles_in_ref(article_ref: str) -> list[str]:
    """`Art. N` keys named in free text; ranges (hyphen or en dash) expand."""
    keys: list[str] = []
    for start, end in _ART.findall(article_ref):
        first = int(start)
        last = int(end) if end else first
        keys.extend(f"Art. {n}" for n in range(first, max(first, last) + 1))
    return list(dict.fromkeys(keys))


def _entry_name(raw: object) -> str:
    if not isinstance(raw, dict):
        raise ValueError(f"timeline entry is not an object: {raw!r}")
    name = raw.get("id")
    if not isinstance(name, str) or not name:
        raise ValueError(f"timeline entry without an id: {raw!r}")
    return name


def _check_common(raw: dict, name: str) -> None:
    """Checks shared by EU and pack entries: text, confidence, review flag, date."""

    def bad(why: str) -> ValueError:
        return ValueError(f"timeline entry {name!r}: {why}")

    for field in ("title", "source", "scope_note"):
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise bad(f"{field} must be a non-empty string")
    if raw.get("confidence") not in _CONFIDENCE:
        raise bad("confidence must be high, medium or low")
    if not isinstance(raw.get("needs_founder_review"), bool):
        raise bad("needs_founder_review must be a boolean")
    applies_from = raw.get("applies_from")
    if applies_from is not None:
        try:
            if not isinstance(applies_from, str):
                raise ValueError
            date.fromisoformat(applies_from)
        except ValueError:
            raise bad(
                f"applies_from {applies_from!r} is not an ISO date or null"
            ) from None


def _parse(raw: object) -> TimelineEntry:
    name = _entry_name(raw)
    assert isinstance(raw, dict)

    def bad(why: str) -> ValueError:
        return ValueError(f"timeline entry {name!r}: {why}")

    _check_common(raw, name)
    refs = raw.get("articles")
    if not isinstance(refs, list) or not refs:
        raise bad("articles must be a non-empty list")
    articles = tuple(
        dict.fromkeys(a for ref in refs for a in articles_in_ref(str(ref)))
    )
    if not articles:
        raise bad("articles names no Art. N")
    basis = raw.get("high_risk_basis")
    if basis is not None and basis not in _BASES:
        raise bad("high_risk_basis must be annex_iii or annex_i")
    return TimelineEntry(
        id=name,
        title=raw["title"],
        applies_from=raw.get("applies_from"),
        articles=articles,
        scope_note=raw["scope_note"],
        source=raw["source"],
        confidence=raw["confidence"],
        needs_founder_review=raw["needs_founder_review"],
        knowledge_ref=raw.get("knowledge_ref"),
        note=raw.get("note"),
        high_risk_basis=basis,
    )


def parse_timeline(data: object) -> tuple[TimelineEntry, ...]:
    """Validate a parsed timeline document; raises ValueError naming the entry."""
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError("regulatory timeline: expected an object with an entries list")
    entries = tuple(_parse(raw) for raw in data["entries"])
    ids = [e.id for e in entries]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        raise ValueError(f"timeline entry {dup!r}: duplicate id")
    return entries


@lru_cache(maxsize=1)
def load_timeline() -> tuple[TimelineEntry, ...]:
    with TIMELINE_PATH.open(encoding="utf-8") as handle:
        return parse_timeline(json.load(handle))


def _order(entry: TimelineEntry) -> tuple[bool, str, str]:
    return (entry.applies_from is None, entry.applies_from or "", entry.id)


def timeline_for_articles(
    articles: Iterable[str], *, bases: Collection[str] | None = None
) -> list[TimelineEntry]:
    """Entries touching any of `articles`, by date (nulls last), then id.

    `bases=None` keeps every entry. Otherwise an entry that names a high-risk
    basis is kept only when that basis is in `bases`.
    """
    wanted = {a for ref in articles for a in articles_in_ref(ref)}
    return sorted(
        (
            e
            for e in load_timeline()
            if wanted.intersection(e.articles)
            and (
                bases is None or e.high_risk_basis is None or e.high_risk_basis in bases
            )
        ),
        key=_order,
    )


_PACK_FIELDS = frozenset(
    {
        "id",
        "title",
        "applies_from",
        "scope_note",
        "source",
        "confidence",
        "needs_founder_review",
        "note",
        "requirements",
        "duration",
    }
)
_PACK_REFUSED = ("high_risk_basis", "knowledge_ref", "articles")


def _parse_pack_entry(raw: object, key: str, row_ids: Collection[str]) -> TimelineEntry:
    name = _entry_name(raw)
    assert isinstance(raw, dict)

    def bad(why: str) -> ValueError:
        return ValueError(f"timeline entry {name!r}: {why}")

    for field in _PACK_REFUSED:
        if field in raw:
            raise bad(f"{field} is not allowed in a pack timeline")
    unknown = sorted(set(raw) - _PACK_FIELDS)
    if unknown:
        raise bad(f"unknown field(s) {', '.join(unknown)}")
    if not name.startswith(f"{key.lower()}."):
        raise bad(f"id must start with {key.lower()}.")
    _check_common(raw, name)
    rows = raw.get("requirements")
    if (
        not isinstance(rows, list)
        or not rows
        or not all(isinstance(r, str) for r in rows)
    ):
        raise bad("requirements must be a non-empty list of row ids")
    missing = [r for r in rows if r not in row_ids]
    if missing:
        raise bad(f"unknown row id(s) {', '.join(missing)} for pack {key}")
    duration = raw.get("duration")
    if duration is not None and (not isinstance(duration, str) or not duration.strip()):
        raise bad("duration must be a non-empty string")
    return TimelineEntry(
        id=name,
        title=raw["title"],
        applies_from=raw.get("applies_from"),
        articles=(),
        scope_note=raw["scope_note"],
        source=raw["source"],
        confidence=raw["confidence"],
        needs_founder_review=raw["needs_founder_review"],
        note=raw.get("note"),
        framework=key,
        requirements=tuple(dict.fromkeys(rows)),
        duration=duration,
    )


def parse_pack_timeline(
    data: object, key: str, row_ids: Collection[str]
) -> tuple[TimelineEntry, ...]:
    """Validate a pack's `timeline.json`; ValueError naming the entry."""
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError(f"{key} timeline: expected an object with an entries list")
    entries = tuple(_parse_pack_entry(raw, key, row_ids) for raw in data["entries"])
    ids = [e.id for e in entries]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        raise ValueError(f"timeline entry {dup!r}: duplicate id")
    return entries


@cache
def load_pack_timeline(key: str) -> tuple[TimelineEntry, ...]:
    """Entries of a pack's `timeline.json`; empty for `none` and `core`."""
    from opencomplai_core.pack_registry import load_pack_meta, pack_file

    meta = load_pack_meta(key)
    mode = meta.get("timeline")
    if mode == "core":
        return ()
    if mode == "none":
        reason = meta.get("timeline_reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError(f"pack {key}: timeline none needs a timeline_reason")
        return ()
    if mode != "file":
        raise ValueError(f"pack {key}: timeline must be core, file or none")
    path = pack_file(key, "timeline.json")
    if path is None:
        raise ValueError(f"pack {key}: timeline is file but timeline.json is missing")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    row_ids: set[str] = set()
    requirements = pack_file(key, str(meta.get("requirements") or ""))
    if requirements is not None:
        with requirements.open(encoding="utf-8") as handle:
            rows = json.load(handle)
        if isinstance(rows, dict):
            row_ids = set(rows)
    return parse_pack_timeline(data, key, row_ids)


def timeline_for_requirements(
    ids: Iterable[str], *, bases: Collection[str] | None = None
) -> list[TimelineEntry]:
    """Entries for any requirement ids, by date (nulls last), then id.

    Unprefixed ids go to the EU timeline; `KEY:` ids to that pack's entries.
    """
    from opencomplai_core.pack_registry import pack_dir

    eu: list[str] = []
    packs: dict[str, set[str]] = {}
    for rid in ids:
        framework, sep, _ = rid.partition(":")
        if sep:
            packs.setdefault(framework, set()).add(rid)
        else:
            eu.append(rid)
    found: dict[tuple[str, str], TimelineEntry] = {
        (e.framework, e.id): e for e in timeline_for_articles(eu, bases=bases)
    }
    for framework, wanted in packs.items():
        if not pack_dir(framework).is_dir():
            continue
        for entry in load_pack_timeline(framework):
            if wanted.intersection(entry.requirements):
                found[(entry.framework, entry.id)] = entry
    return sorted(found.values(), key=_order)


def timeline_ids(requirement_id: str) -> list[str]:
    """Ids of the timeline entries that touch one requirement id."""
    return [e.id for e in timeline_for_requirements([requirement_id])]


def today_utc() -> date:
    return datetime.now(UTC).date()


def status_on(entry: TimelineEntry, today: date) -> Status:
    if entry.applies_from is None:
        return "unconfirmed"
    return "in_force" if date.fromisoformat(entry.applies_from) <= today else "upcoming"


def date_text(entry: TimelineEntry) -> str:
    return entry.applies_from or "date unconfirmed"


def provenance(entry: TimelineEntry) -> str:
    review = "; pending founder review" if entry.needs_founder_review else ""
    return f"{entry.source}; confidence {entry.confidence}{review}"


def format_entry(entry: TimelineEntry, today: date | None = None) -> str:
    """`<date> - <title> [<source>; confidence <c>; pending founder review]`,
    plus ` (in force|upcoming)` when `today` is given and the date is known."""
    text = f"{date_text(entry)} - {entry.title} [{provenance(entry)}]"
    if entry.duration:
        text += f" ({entry.duration})"
    if today is not None:
        status = status_on(entry, today)
        if status != "unconfirmed":
            text += f" ({status.replace('_', ' ')})"
    return text


def timeline_lines(articles: Iterable[str], today: date | None = None) -> list[str]:
    """Plain lines for a block under a `Regulatory timeline` heading; [] if none."""
    return [format_entry(e, today) for e in timeline_for_articles(articles)]


def knowledge_dates() -> dict[str, str]:
    """`applies_from` read from the knowledge modules, keyed like `knowledge_ref`."""
    from opencomplai_core.knowledge.limited_risk import LIMITED_RISK
    from opencomplai_core.knowledge.prohibited import PROHIBITED

    added = ("Art.5(1)(ba)", "Art.5(1)(bb)")  # Reg. (EU) 2026/1744, Art. 1(7)
    first = [p.applies_from for p in PROHIBITED if p.article not in added]
    return {
        "prohibited:*:min": min(first),
        **{
            f"prohibited:{point}": next(
                p.applies_from for p in PROHIBITED if p.article == point
            )
            for point in added
        },
        "limited_risk:*": min(e.applies_from for e in LIMITED_RISK),
    }
