"""Validate a framework pack, or a probe file, against the agreed data shape.

Usage (from the repo root):
  uv run python tools/packs/validate_pack.py <KEY> [--strict]
  uv run python tools/packs/validate_pack.py --all [--strict]
  uv run python tools/packs/validate_pack.py --probes <file.json>

Exit 0 and a summary line when valid; exit 1 with every problem listed otherwise.
Base mode passes on today's pack data; strict mode is what a pack card has to
satisfy. `validate(key, strict)` and `validate_probe_file(path)` return the
problem lists.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from opencomplai_core import applicability, gap_probes
from opencomplai_core.evaluators.registry import EVALUATOR_REGISTRY
from opencomplai_core.probe_registry import parse_probe_file

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "packages/core/src/opencomplai_core"
PACKS_DIR = CORE / "packs"
EU_KEY = "EU_AI_ACT"
NIST_KEY = "NIST_AI_RMF"

ANNEX_A = {
    f"A.{t}.{n}"
    for t, last in ((5, 37), (6, 8), (7, 14), (8, 34))
    for n in range(1, last + 1)
}
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ().,\-/]*$")
FIELDS = {
    "title",
    "note",
    "default_ttl_days",
    "sources",
    "eu_ai_act",
    "iso_27001",
    "iso_42001",
    "source",
    "confidence",
    "needs_founder_review",
    "evidence_class",
    "why_attestation",
    "scope_out",
    "own_wording",
    "review_ref",
    "nist_ai_rmf",
    "soc2",
    "iso_27090",
}
REQUIRED = {
    "title",
    "default_ttl_days",
    "sources",
    "eu_ai_act",
    "source",
    "confidence",
    "needs_founder_review",
}
LINK_LISTS = ("eu_ai_act", "iso_27001", "iso_42001", "nist_ai_rmf", "soc2", "iso_27090")
TTLS = (30, 90, 180, 365, 730)
KINDS = {
    "attestation",
    "artifact",
    "evaluator",
    "scan",
    "manifest",
    "record",
    "crosswalk",
}
ROLES = {"supporting", "corroborating"}
CORROBORATING_KINDS = {"artifact", "evaluator", "scan"}
CLASSES = {"machine", "hybrid", "organisational"}
DOC_SUFFIXES = (".md", ".txt", ".pdf", ".docx")
WHY_MAX = 160


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _eu_ids() -> set[str]:
    data = _load(CORE / "data/gap_article_map.json")
    return {k for k in data if not k.startswith("_")}


def _row_ids(key: str) -> set[str]:
    path = PACKS_DIR / key / "requirements.json"
    return set(_load(path)) if path.is_file() else set()


def _scope_keys(scope_out: Any) -> list[Any]:
    """Flatten a scope_out value (a list of key lists, a list of keys or a map)."""
    if isinstance(scope_out, dict):
        return list(scope_out)
    out: list[Any] = []
    if isinstance(scope_out, list):
        for item in scope_out:
            out.extend(item if isinstance(item, list) else [item])
        return out
    return [scope_out]


def _one_line(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value


def pack_keys() -> list[str]:
    """Keys of the non-EU packs that have a requirements file."""
    if not PACKS_DIR.is_dir():
        return []
    return sorted(
        d.name
        for d in PACKS_DIR.iterdir()
        if d.is_dir() and d.name != EU_KEY and (d / "requirements.json").is_file()
    )


def validate_rows(
    key: str,
    rows: Any,
    *,
    strict: bool = False,
    copyright_: str | None = None,
    scope_keys: set[str] | None = None,
) -> list[str]:
    """Problems found in the requirement rows of pack `key`."""
    if not isinstance(rows, dict) or not rows:
        return ["file must be a non-empty JSON object"]
    if scope_keys is None:
        scope_keys = set(applicability.declared_scope_keys(key))
    eu, iso42 = _eu_ids(), _row_ids("ISO_IEC_42001")
    evaluators = {e.evaluator_id for e in EVALUATOR_REGISTRY}
    errs: list[str] = []
    for rid, row in rows.items():
        if not rid.startswith(f"{key}:") or not ID.match(rid.split(":", 1)[1]):
            errs.append(
                f"{rid}: id must be '{key}:<id>' with letters, digits, spaces, ().,-/"
            )
        if not isinstance(row, dict):
            errs.append(f"{rid}: row must be an object")
            continue
        errs.extend(
            _row_problems(
                key, rid, row, strict, copyright_, scope_keys, eu, iso42, evaluators
            )
        )
    if strict and len(rows) > 10:
        ttls = {r.get("default_ttl_days") for r in rows.values() if isinstance(r, dict)}
        if len(ttls) < 2:
            errs.append(
                f"{key}: more than 10 rows need two or more default_ttl_days values"
            )
    return errs


def _row_problems(
    key, rid, row, strict, copyright_, scope_keys, eu, iso42, evaluators
) -> list[str]:
    errs: list[str] = []
    if missing := REQUIRED - set(row):
        errs.append(f"{rid}: missing {sorted(missing)}")
    if extra := set(row) - FIELDS:
        errs.append(f"{rid}: unknown fields {sorted(extra)}")
    title = row.get("title")
    if (
        not isinstance(title, str)
        or not title.strip()
        or (copyright_ != "public_domain" and len(title.strip()) > 80)
    ):
        errs.append(f"{rid}: title must be 1-80 characters")
    if "note" in row and not _one_line(row["note"]):
        errs.append(f"{rid}: note must be one non-empty line")
    if row.get("default_ttl_days") not in TTLS:
        errs.append(f"{rid}: default_ttl_days must be one of {list(TTLS)}")
    errs.extend(_source_problems(key, rid, row, evaluators))
    if "evidence_class" in row and row["evidence_class"] not in CLASSES:
        errs.append(f"{rid}: evidence_class must be one of {sorted(CLASSES)}")
    if "why_attestation" in row and not _one_line(row["why_attestation"]):
        errs.append(f"{rid}: why_attestation must be one non-empty line")
    if "own_wording" in row and not isinstance(row["own_wording"], bool):
        errs.append(f"{rid}: own_wording must be true or false")
    if "review_ref" in row and not _one_line(row["review_ref"]):
        errs.append(f"{rid}: review_ref must be one non-empty line")
    if "scope_out" in row:
        bad = [k for k in _scope_keys(row["scope_out"]) if k not in scope_keys]
        if bad:
            errs.append(f"{rid}: scope_out keys not declared for {key}: {bad}")
    for field in LINK_LISTS:
        values = row.get(field, [])
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            errs.append(f"{rid}: {field} must be a list of strings")
        elif len(values) != len(set(values)):
            errs.append(f"{rid}: duplicate entries in {field}")
    if isinstance(row.get("eu_ai_act"), list) and (
        bad := [a for a in row["eu_ai_act"] if a not in eu]
    ):
        errs.append(f"{rid}: eu_ai_act entries not in gap_article_map.json: {bad}")
    if isinstance(row.get("iso_27001"), list):
        if key == "ISO_IEC_27001":
            errs.append(f"{rid}: the ISO 27001 pack carries no iso_27001 field")
        elif bad := [a for a in row["iso_27001"] if a not in ANNEX_A]:
            errs.append(
                f"{rid}: iso_27001 entries must be Annex A ids A.5.1-A.8.34: {bad}"
            )
    if isinstance(row.get("iso_42001"), list) and (
        bad := [a for a in row["iso_42001"] if a not in iso42]
    ):
        errs.append(
            f"{rid}: iso_42001 entries not rows of the ISO_IEC_42001 pack: {bad}"
        )
    if not isinstance(row.get("source"), str) or not row["source"].strip():
        errs.append(f"{rid}: source must be a non-empty string")
    if row.get("needs_founder_review") is not True:
        errs.append(f"{rid}: needs_founder_review must stay true")
    conf = row.get("confidence")
    if conf not in ("low", "medium", "high"):
        errs.append(f"{rid}: confidence must be low, medium or high")
    elif conf != "low" and not row.get("review_ref"):
        errs.append(f"{rid}: confidence above low needs a review_ref")
    if strict:
        errs.extend(_strict_problems(rid, row, copyright_))
    return errs


def _source_problems(key, rid, row, evaluators) -> list[str]:
    errs: list[str] = []
    sources = row.get("sources")
    if not isinstance(sources, list) or not all(isinstance(s, dict) for s in sources):
        return [f"{rid}: sources must be a list of objects"]
    att = [s for s in sources if s.get("kind") == "attestation"]
    if len(att) == 1:
        if att[0].get("ref") != rid:
            errs.append(f"{rid}: the attestation source must have ref '{rid}'")
    elif not (key == NIST_KEY and not att):
        errs.append(
            f"{rid}: exactly one attestation source is required, found {len(att)}"
        )
    for s in sources:
        kind, role, ref = s.get("kind"), s.get("role"), s.get("ref")
        if kind not in KINDS or (kind == "crosswalk" and key != NIST_KEY):
            errs.append(f"{rid}: source kind {kind!r} is not allowed here")
            continue
        if kind == "crosswalk" and ref != rid:
            errs.append(f"{rid}: the crosswalk source must have ref '{rid}'")
        if role is not None:
            if role not in ROLES:
                errs.append(
                    f"{rid}: source role must be absent, supporting or corroborating: {s}"
                )
            elif role == "corroborating" and kind not in CORROBORATING_KINDS:
                errs.append(
                    f"{rid}: corroborating role only on artifact, evaluator or scan: {s}"
                )
        if kind == "artifact" and not (
            isinstance(ref, str) and gap_probes.probe_exists(ref)
        ):
            errs.append(f"{rid}: artifact ref is not a known probe: {ref!r}")
        if kind == "evaluator" and ref not in evaluators:
            errs.append(f"{rid}: evaluator ref is not in EVALUATOR_REGISTRY: {ref!r}")
    return errs


def _strict_problems(rid: str, row: dict, copyright_: str | None) -> list[str]:
    errs: list[str] = []
    if "note" not in row:
        errs.append(f"{rid}: strict: note is required")
    cls = row.get("evidence_class")
    if cls is None:
        errs.append(f"{rid}: strict: evidence_class is required")
    note = row.get("note")
    if (
        copyright_ == "restricted"
        and isinstance(note, str)
        and not (note.startswith("Evidence that") or row.get("own_wording") is True)
    ):
        errs.append(
            f"{rid}: strict: in a restricted pack the note starts with 'Evidence that' or own_wording is true"
        )
    sources = [s for s in row.get("sources", []) if isinstance(s, dict)]
    if cls in ("machine", "hybrid") and not any(
        s.get("kind") != "attestation" and s.get("role") != "supporting"
        for s in sources
    ):
        errs.append(
            f"{rid}: strict: a {cls} row needs a source that is neither attestation nor supporting"
        )
    if cls == "organisational":
        why = row.get("why_attestation")
        if not _one_line(why) or len(why) > WHY_MAX:
            errs.append(
                f"{rid}: strict: an organisational row needs a one-line why_attestation of at most {WHY_MAX} characters"
            )
    return errs


def validate(key: str, strict: bool = False) -> list[str]:
    """Every problem found in the pack `key`; empty when it is valid."""
    if key == EU_KEY:
        return [f"{key}: the EU AI Act pack is frozen and not validated here"]
    pack_dir = PACKS_DIR / key
    path = pack_dir / "requirements.json"
    if not path.is_file():
        return [f"{key}: no requirements file at {path}"]
    try:
        rows = _load(path)
    except ValueError as exc:
        return [f"{path}: cannot read: {exc}"]
    copyright_ = None
    meta_path = pack_dir / "pack.json"
    if meta_path.is_file():
        try:
            copyright_ = _load(meta_path).get("copyright")
        except (ValueError, AttributeError) as exc:
            return [f"{meta_path}: cannot read: {exc}"]
    errs: list[str] = []
    try:
        scope = set(applicability.declared_scope_keys(key))
    except ValueError as exc:
        errs.append(f"{key}: applicability.json: {exc}")
        scope = set(applicability.load_scope_keys())
    errs.extend(
        validate_rows(key, rows, strict=strict, copyright_=copyright_, scope_keys=scope)
    )
    return errs


def validate_probe_file(path: Path | str) -> list[str]:
    """Problems found in one probe file."""
    path = Path(path)
    prefix = None
    if path.name == "probes.json" and path.resolve().parent.parent.name == "packs":
        prefix = path.resolve().parent.name.lower()
    try:
        probes = parse_probe_file(path, prefix=prefix)
    except ValueError as exc:
        return [str(exc)]
    errs: list[str] = []
    for ref, probe in probes.items():
        if probe.provenance is None:
            errs.append(f"{ref}: provenance is required")
        has_doc = any(str(p).lower().endswith(DOC_SUFFIXES) for p in probe.patterns)
        if has_doc and probe.markers is None and not probe.clauses:
            errs.append(f"{ref}: a probe with a document pattern needs markers")
    return errs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("key", nargs="?", help="pack key, e.g. ISO_IEC_27001")
    ap.add_argument(
        "--all", action="store_true", help="every non-EU pack with a requirements file"
    )
    ap.add_argument(
        "--strict", action="store_true", help="the stricter rules a pack card must meet"
    )
    ap.add_argument(
        "--probes", metavar="FILE", help="validate a probe file instead of a pack"
    )
    args = ap.parse_args(argv)
    if args.probes:
        problems = validate_probe_file(args.probes)
        summary = f"OK {args.probes}"
    elif args.all:
        keys = pack_keys()
        problems = [f"{k}: {p}" for k in keys for p in validate(k, args.strict)]
        summary = f"OK {len(keys)} packs{' (strict)' if args.strict else ''}"
    elif args.key:
        problems = validate(args.key, args.strict)
        summary = f"OK {args.key}{' (strict)' if args.strict else ''}"
    else:
        ap.error("give a pack key, --all or --probes")
    if problems:
        print("\n".join(problems))
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
