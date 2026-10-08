"""Regulatory timeline: when each EU AI Act obligation starts to apply.

Presentation-only lookup over `data/regulatory_timeline.json`. It never feeds
the checker engine, `obligations.json` or any signed or ingested shape. Every
date is flagged for founder review; a `null` date is shown as "date
unconfirmed", never guessed. Status wording takes an injected `today` (E-14).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

TIMELINE_PATH = Path(__file__).resolve().parent / "data" / "regulatory_timeline.json"

_CONFIDENCE = frozenset({"high", "medium", "low"})
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
    knowledge_ref: str | None = None
    note: str | None = None


def articles_in_ref(article_ref: str) -> list[str]:
    """`Art. N` keys named in free text; ranges (hyphen or en dash) expand."""
    keys: list[str] = []
    for start, end in _ART.findall(article_ref):
        first = int(start)
        last = int(end) if end else first
        keys.extend(f"Art. {n}" for n in range(first, max(first, last) + 1))
    return list(dict.fromkeys(keys))


def _parse(raw: object) -> TimelineEntry:
    if not isinstance(raw, dict):
        raise ValueError(f"timeline entry is not an object: {raw!r}")
    name = raw.get("id")
    if not isinstance(name, str) or not name:
        raise ValueError(f"timeline entry without an id: {raw!r}")

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
    refs = raw.get("articles")
    if not isinstance(refs, list) or not refs:
        raise bad("articles must be a non-empty list")
    articles = tuple(
        dict.fromkeys(a for ref in refs for a in articles_in_ref(str(ref)))
    )
    if not articles:
        raise bad("articles names no Art. N")
    return TimelineEntry(
        id=name,
        title=raw["title"],
        applies_from=applies_from,
        articles=articles,
        scope_note=raw["scope_note"],
        source=raw["source"],
        confidence=raw["confidence"],
        needs_founder_review=raw["needs_founder_review"],
        knowledge_ref=raw.get("knowledge_ref"),
        note=raw.get("note"),
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


def timeline_for_articles(articles: Iterable[str]) -> list[TimelineEntry]:
    """Entries touching any of `articles`, by date (nulls last), then id."""
    wanted = {a for ref in articles for a in articles_in_ref(ref)}
    return sorted(
        (e for e in load_timeline() if wanted.intersection(e.articles)), key=_order
    )


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

    ninth = "Art.5(1)(i)"
    first = [p.applies_from for p in PROHIBITED if p.article != ninth]
    return {
        "prohibited:*:min": min(first),
        f"prohibited:{ninth}": next(
            p.applies_from for p in PROHIBITED if p.article == ninth
        ),
        "limited_risk:*": min(e.applies_from for e in LIMITED_RISK),
    }
