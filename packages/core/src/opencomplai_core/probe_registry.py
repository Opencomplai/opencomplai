"""Artifact probes declared as data: parsing of `probes/<family>.json` and
`packs/<KEY>/probes.json`. Standard library only; `gap_probes.py` turns the
parsed definitions into its lookup tables.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from opencomplai_core import pack_registry

SHARED_PROBES_DIR = Path(__file__).resolve().parent / "probes"
PACK_PROBES_FILE = "probes.json"

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_FLAG_BITS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}

_PROBE_KEYS = {"patterns", "markers", "code_hint", "provenance"}
_CLAUSE_PROBE_KEYS = {"type", "patterns", "noun", "provenance", "clauses"}
_CLAUSE_DOCUMENT = "clause_document"
_CLAUSE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ().,/-]*$")
_MARKER_KEYS = {
    "all",
    "found_label",
    "lacks_label",
    "noun",
    "body_only",
    "forbid_scaffold",
    "select",
    "note",
}
_BOOL_MARKER_KEYS = ("body_only", "forbid_scaffold", "select")
_PROVENANCE_KEYS = {"source", "confidence", "needs_founder_review"}


@dataclass(frozen=True)
class ProbeDef:
    """One parsed probe. `markers` is a dict whose `all` is a list of
    (pattern, flags) pairs, or None; `code_hint` is a (pattern, flags) pair."""

    ref: str
    patterns: tuple[str, ...]
    markers: dict[str, Any] | None = None
    code_hint: tuple[str, str] | None = None
    provenance: dict[str, Any] | None = None
    # Clause-document probes only: the noun, and clause id -> {"title": str,
    # "markers": [(pattern, flags), ...]} in file order.
    noun: str | None = None
    clauses: dict[str, dict[str, Any]] | None = None


def flags_to_int(flags: str) -> int:
    value = 0
    for letter in flags:
        value |= _FLAG_BITS[letter]
    return value


def flags_to_letters(flags: int) -> str:
    return "".join(letter for letter, bit in _FLAG_BITS.items() if flags & bit)


def _regex(path: Path, ref: str, where: str, entry: Any) -> tuple[str, str]:
    if not isinstance(entry, dict) or set(entry) - {"re", "flags"}:
        raise ValueError(
            f"{path}: probe {ref!r}: {where} must be an object with 're' and 'flags'"
        )
    pattern = entry.get("re")
    flags = entry.get("flags", "")
    if not isinstance(pattern, str) or not pattern:
        raise ValueError(f"{path}: probe {ref!r}: {where} needs a non-empty 're'")
    if not isinstance(flags, str) or set(flags) - set(_FLAG_BITS):
        raise ValueError(f"{path}: probe {ref!r}: {where} flags may only use i, m, s")
    try:
        re.compile(pattern, flags_to_int(flags))
    except re.error as exc:
        raise ValueError(
            f"{path}: probe {ref!r}: {where} is not a valid regex: {exc}"
        ) from exc
    return pattern, "".join(letter for letter in "ims" if letter in flags)


def _text(path: Path, ref: str, where: str, value: Any, *, required: bool) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value):
        raise ValueError(f"{path}: probe {ref!r}: {where} must be a non-empty string")
    return value


def _parse_markers(path: Path, ref: str, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: probe {ref!r}: markers must be an object")
    unknown = set(raw) - _MARKER_KEYS
    if unknown:
        raise ValueError(
            f"{path}: probe {ref!r}: unknown markers key(s) {sorted(unknown)}"
        )
    entries = raw.get("all")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{path}: probe {ref!r}: markers.all must be a non-empty list")
    out: dict[str, Any] = {
        "all": [
            _regex(path, ref, f"markers.all[{i}]", e) for i, e in enumerate(entries)
        ]
    }
    for key in ("found_label", "lacks_label", "noun"):
        out[key] = _text(path, ref, f"markers.{key}", raw.get(key), required=True)
    out["note"] = _text(path, ref, "markers.note", raw.get("note"), required=False)
    for key in _BOOL_MARKER_KEYS:
        value = raw.get(key, False)
        if not isinstance(value, bool):
            raise ValueError(
                f"{path}: probe {ref!r}: markers.{key} must be true or false"
            )
        out[key] = value
    return out


def _parse_provenance(path: Path, ref: str, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) - _PROVENANCE_KEYS:
        raise ValueError(
            f"{path}: probe {ref!r}: provenance must be an object with "
            "source, confidence, needs_founder_review"
        )
    out: dict[str, Any] = {
        "source": _text(
            path, ref, "provenance.source", raw.get("source"), required=True
        ),
        "confidence": _text(
            path, ref, "provenance.confidence", raw.get("confidence"), required=True
        ),
    }
    if "needs_founder_review" in raw:
        if not isinstance(raw["needs_founder_review"], bool):
            raise ValueError(
                f"{path}: probe {ref!r}: provenance.needs_founder_review "
                "must be true or false"
            )
        out["needs_founder_review"] = raw["needs_founder_review"]
    return out


def _parse_clauses(path: Path, ref: str, raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError(f"{path}: probe {ref!r}: clauses must be a non-empty object")
    out: dict[str, dict[str, Any]] = {}
    for clause, body in raw.items():
        if not _CLAUSE_ID.match(clause):
            raise ValueError(
                f"{path}: probe {ref!r}: clause id {clause!r} must match "
                f"{_CLAUSE_ID.pattern}"
            )
        if not isinstance(body, dict) or set(body) - {"title", "markers"}:
            raise ValueError(
                f"{path}: probe {ref!r}: clause {clause!r} must be an object "
                "with 'title' and 'markers'"
            )
        title = _text(
            path, ref, f"clauses.{clause}.title", body.get("title"), required=True
        )
        markers = body.get("markers")
        if not isinstance(markers, list) or not markers:
            raise ValueError(
                f"{path}: probe {ref!r}: clause {clause!r} needs at least one marker"
            )
        out[clause] = {
            "title": title,
            "markers": [
                _regex(path, ref, f"clauses.{clause}.markers[{i}]", m)
                for i, m in enumerate(markers)
            ],
        }
    return out


def _parse_clause_document(path: Path, ref: str, body: dict[str, Any]) -> ProbeDef:
    unknown = set(body) - _CLAUSE_PROBE_KEYS
    if unknown:
        raise ValueError(
            f"{path}: probe {ref!r}: unknown key(s) {sorted(unknown)} "
            "for a clause_document probe"
        )
    missing = {"noun", "provenance", "clauses"} - set(body)
    if missing:
        raise ValueError(
            f"{path}: probe {ref!r}: clause_document needs {sorted(missing)}"
        )
    return ProbeDef(
        ref=ref,
        patterns=_patterns(path, ref, body.get("patterns")),
        provenance=_parse_provenance(path, ref, body["provenance"]),
        noun=_text(path, ref, "noun", body["noun"], required=True),
        clauses=_parse_clauses(path, ref, body["clauses"]),
    )


def _patterns(path: Path, ref: str, patterns: Any) -> tuple[str, ...]:
    if (
        not isinstance(patterns, list)
        or not patterns
        or not all(isinstance(p, str) and p for p in patterns)
    ):
        raise ValueError(
            f"{path}: probe {ref!r}: patterns must be a non-empty list of strings"
        )
    return tuple(patterns)


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate key {key!r}")
        out[key] = value
    return out


def _check_ref(path: Path, ref: str, prefix: str | None) -> None:
    if prefix is None:
        if not _NAME.match(ref):
            raise ValueError(
                f"{path}: probe ref {ref!r} must match ^[a-z][a-z0-9_]*$ "
                "in a shared file"
            )
        return
    head, dot, tail = ref.partition(".")
    if head != prefix.lower() or not dot or not _NAME.match(tail):
        raise ValueError(
            f"{path}: probe ref {ref!r} must start with '{prefix.lower()}.' "
            "followed by ^[a-z][a-z0-9_]*$ in a pack-local file"
        )


def parse_probe_file(path: Path, prefix: str | None = None) -> dict[str, ProbeDef]:
    """Parse one probe file. `prefix` is the lower-case pack key of a
    pack-local file (refs must read `<prefix>.<name>`), None for a shared one."""
    path = Path(path)
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_no_duplicate_keys
        )
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path}: cannot read probe file: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"family", "probes"}:
        raise ValueError(
            f"{path}: expected an object with exactly 'family' and 'probes'"
        )
    if not isinstance(data["family"], str) or not data["family"]:
        raise ValueError(f"{path}: 'family' must be a non-empty string")
    probes = data["probes"]
    if not isinstance(probes, dict):
        raise ValueError(f"{path}: 'probes' must be an object")
    out: dict[str, ProbeDef] = {}
    for ref, body in probes.items():
        _check_ref(path, ref, prefix)
        if not isinstance(body, dict):
            raise ValueError(f"{path}: probe {ref!r} must be an object")
        kind = body.get("type")
        if kind is not None:
            if kind != _CLAUSE_DOCUMENT:
                raise ValueError(
                    f"{path}: probe {ref!r}: unknown type {kind!r} "
                    f"(only {_CLAUSE_DOCUMENT!r})"
                )
            out[ref] = _parse_clause_document(path, ref, body)
            continue
        unknown = set(body) - _PROBE_KEYS
        if unknown:
            raise ValueError(f"{path}: probe {ref!r}: unknown key(s) {sorted(unknown)}")
        patterns = _patterns(path, ref, body.get("patterns"))
        out[ref] = ProbeDef(
            ref=ref,
            patterns=patterns,
            markers=_parse_markers(path, ref, body["markers"])
            if "markers" in body
            else None,
            code_hint=_regex(path, ref, "code_hint", body["code_hint"])
            if "code_hint" in body
            else None,
            provenance=_parse_provenance(path, ref, body["provenance"])
            if "provenance" in body
            else None,
        )
    return out


def iter_probe_files() -> Iterator[tuple[Path, str | None]]:
    """(path, prefix) of every probe file: shared files by name (prefix None),
    then each discovered pack's `probes.json` (prefix = lower-case pack key)."""
    if SHARED_PROBES_DIR.is_dir():
        for path in sorted(SHARED_PROBES_DIR.glob("*.json"), key=lambda p: p.name):
            yield path, None
    for meta in pack_registry.discover_packs():
        pack_probes = pack_registry.pack_file(meta["id"], PACK_PROBES_FILE)
        if pack_probes is not None:
            yield pack_probes, str(meta["id"]).lower()
