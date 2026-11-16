"""Decide, without judgement, how close a framework pack is to the EU AI Act pack.

Usage (from the repo root):
  uv run python tools/packs/parity_check.py <KEY> [--json]
  uv run python tools/packs/parity_check.py --all [--json]
  add --gate to also require the docs page in docs/mkdocs.yml (P15)
  add --write-status to write the derived status into pack.json

Fifteen capabilities P1 to P15 define parity. Text output is one line per capability,
`P<n> pass|fail|pending <detail>`. Exit 0 only when nothing fails or is pending.
Passing says the pack's plumbing works like the EU AI Act pack, not that its
rows are green.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pack_doc
import packfmt
from opencomplai_core import (
    applicability,
    pack_registry,
    pack_scaffolds,
    regulatory_timeline,
)
from opencomplai_core.evaluators.registry import EVALUATOR_REGISTRY
from opencomplai_core.gap_probes import probe_exists
from validate_pack import validate

REPO = Path(__file__).resolve().parents[2]
GOLDEN_DIR = REPO / "packages/cli/tests/golden/packs"
FIXTURE_DIR = REPO / "packages/core/tests/fixtures/packs"
EU_KEY = "EU_AI_ACT"
NIST_KEY = "NIST_AI_RMF"
MKDOCS = REPO / "docs" / "mkdocs.yml"
PASS, FAIL, PENDING = "pass", "fail", "pending"
PACK_FILES = ("applicability.json", "probes.json", "timeline.json")
SHARE_FLOOR_PERCENT = 85
EVIDENCED_CONFIDENCE = 0.6
VERDICT_WORDS = {"met", "partial", "missing", "unverified"}
GAP_GOLDENS = ("gaps_empty", "gaps_scaffolded", "gaps_evidenced")
REPORT_GOLDENS = (
    "check_reports.junit.xml",
    "check_reports.sarif.json",
    "check_reports.summary.md",
)
FIXTURE_ENTRIES = ("manifest.json", "empty", "scaffolded", "evidenced")
PLACEHOLDER_REASON = "not yet assessed"
MAX_SCAFFOLDS = 4
_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December"
)
DATE_RE = re.compile(
    rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\s+\d{{4}}\b",
    re.IGNORECASE,
)

Result = tuple[str, str]


@dataclass
class Ctx:
    """Everything a check reads; tests build one from small dicts."""

    key: str
    pack_path: Path = field(default_factory=Path)
    golden: Path = field(default_factory=Path)
    fixtures: Path = field(default_factory=Path)
    meta: dict[str, Any] = field(default_factory=dict)
    rows: dict[str, Any] = field(default_factory=dict)
    applicability: dict[str, Any] | None = None
    applicability_error: str | None = None
    scope_keys: set[str] = field(default_factory=set)
    strict_problems: list[str] = field(default_factory=list)
    evaluators: set[str] = field(default_factory=set)
    gate: bool = False


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_ctx(key: str, gate: bool = False) -> Ctx:
    """Read the pack's data once; unreadable parts stay empty and the checks say so."""
    path = pack_registry.pack_dir(key)
    ctx = Ctx(
        key=key,
        pack_path=path,
        golden=GOLDEN_DIR / key,
        fixtures=FIXTURE_DIR / key,
        gate=gate,
    )
    try:
        ctx.meta = pack_registry.load_pack_meta(key)
    except ValueError:
        try:
            ctx.meta = _read(path / pack_registry.PACK_FILE)
        except (OSError, ValueError):
            ctx.meta = {}
    req = path / "requirements.json"
    try:
        rows = _read(req) if req.is_file() else {}
    except (OSError, ValueError):
        rows = {}
    ctx.rows = rows if isinstance(rows, dict) else {}
    try:
        ctx.applicability = applicability.load_applicability(key)
        ctx.scope_keys = set(applicability.declared_scope_keys(key))
    except ValueError as exc:
        ctx.applicability_error = str(exc)
        ctx.scope_keys = set(applicability.load_scope_keys())
    ctx.strict_problems = validate(key, strict=True)
    ctx.evaluators = {e.evaluator_id for e in EVALUATOR_REGISTRY}
    return ctx


def _scope_keys(scope_out: Any) -> list[Any]:
    if isinstance(scope_out, dict):
        return list(scope_out)
    if isinstance(scope_out, list):
        out: list[Any] = []
        for item in scope_out:
            out.extend(item if isinstance(item, list) else [item])
        return out
    return [scope_out]


def _golden_json(ctx: Ctx, name: str) -> tuple[Any, str | None]:
    path = ctx.golden / name
    if not path.is_file():
        return None, f"no golden {name}"
    try:
        return _read(path), None
    except (OSError, ValueError) as exc:
        return None, f"golden {name} unreadable: {exc}"


def _gap_rows(data: Any, key: str) -> list[dict[str, Any]]:
    """Article rows of a `gaps` golden: the pack's own report when present."""
    node = data.get("payload", data) if isinstance(data, dict) else {}
    fw = node.get("frameworks", {}).get(key) if isinstance(node, dict) else None
    if isinstance(fw, dict):
        node = fw.get("report", fw)
    rows = node.get("articles", []) if isinstance(node, dict) else []
    return [r for r in rows if isinstance(r, dict)]


def _lists_excluded(node: Any, key: str) -> bool:
    if isinstance(node, dict):
        excluded = node.get("excluded")
        if isinstance(excluded, dict) and any(
            str(k).startswith(f"{key}:") for k in excluded
        ):
            return True
        return any(_lists_excluded(v, key) for v in node.values())
    if isinstance(node, list):
        return any(_lists_excluded(v, key) for v in node)
    return False


def check_p1(ctx: Ctx) -> Result:
    """Applicability: loads, outcomes have goldens, data files are listed."""
    if ctx.applicability_error:
        return FAIL, ctx.applicability_error
    if ctx.applicability is None:
        return FAIL, "no applicability.json"
    data = ctx.applicability
    outcomes = {data["default"], *(r["outcome"] for r in data.get("outcomes", []))}
    absent = sorted(
        o for o in outcomes if not (ctx.golden / f"applicability_{o}.json").is_file()
    )
    if absent:
        return FAIL, f"no golden applicability_<outcome>.json for {', '.join(absent)}"
    listed = {Path(str(p)).name for p in ctx.meta.get("data_files", [])}
    unlisted = [
        n for n in PACK_FILES if (ctx.pack_path / n).is_file() and n not in listed
    ]
    if unlisted:
        return FAIL, f"not listed in pack.json data_files: {', '.join(unlisted)}"
    return PASS, f"{len(outcomes)} outcome(s) with goldens"


def check_p2(ctx: Ctx) -> Result:
    """Row scoping: scope_out keys are declared; a golden shows an exclusion."""
    scoped = {
        rid: r["scope_out"]
        for rid, r in ctx.rows.items()
        if isinstance(r, dict) and "scope_out" in r
    }
    if not scoped:
        return PASS, "no scoped rows"
    bad = sorted(
        f"{rid}: {k}"
        for rid, value in scoped.items()
        for k in _scope_keys(value)
        if k not in ctx.scope_keys
    )
    if bad:
        return FAIL, f"scope_out keys not declared: {'; '.join(bad)}"
    if ctx.golden.is_dir():
        for path in sorted(ctx.golden.glob("*.json")):
            try:
                if _lists_excluded(_read(path), ctx.key):
                    return PASS, f"{len(scoped)} scoped row(s); excluded in {path.name}"
            except (OSError, ValueError):
                continue
    return FAIL, "no golden lists a row of this pack as excluded"


def _problems(ctx: Ctx, *needles: str) -> list[str]:
    return [p for p in ctx.strict_problems if any(n in p for n in needles)]


def check_p3(ctx: Ctx) -> Result:
    """Classification: no strict problem about evidence_class or why_attestation."""
    found = _problems(ctx, "evidence_class", "why_attestation")
    if found:
        return FAIL, f"{len(found)} problem(s), first: {found[0]}"
    return PASS, "evidence_class and why_attestation valid"


def check_p7(ctx: Ctx) -> Result:
    """Freshness: no strict problem about TTL values."""
    found = _problems(ctx, "default_ttl_days")
    if found:
        return FAIL, f"{len(found)} problem(s), first: {found[0]}"
    return PASS, "default_ttl_days valid"


def _counts(ctx: Ctx) -> dict[str, int]:
    out = {"machine": 0, "hybrid": 0, "organisational": 0}
    for row in ctx.rows.values():
        cls = row.get("evidence_class") if isinstance(row, dict) else None
        out[cls if cls in out else "organisational"] += 1
    return out


def check_p4(ctx: Ctx) -> Result:
    """Machine sources: classed rows resolve; the machine share meets the target."""
    for rid, row in ctx.rows.items():
        if not isinstance(row, dict) or row.get("evidence_class") not in (
            "machine",
            "hybrid",
        ):
            continue
        sources = [
            s
            for s in row.get("sources", [])
            if isinstance(s, dict) and s.get("kind") != "attestation"
        ]
        if not sources:
            return FAIL, f"{rid}: no non-attestation source"
        for s in sources:
            kind, ref = s.get("kind"), s.get("ref")
            if kind == "artifact":
                ok = isinstance(ref, str) and probe_exists(ref)
            elif kind == "evaluator":
                ok = ref in ctx.evaluators
            else:
                ok = isinstance(ref, str) and bool(ref.strip())
            if not ok:
                return FAIL, f"{rid}: {kind} source {ref!r} does not resolve"
    counts = _counts(ctx)
    have = counts["machine"] + counts["hybrid"]
    target = ctx.meta.get("target_machine_share", 0)
    floor = math.floor(target * SHARE_FLOOR_PERCENT / 100)
    detail = (
        f"machine+hybrid {have} of {len(ctx.rows)} rows, target {target}, floor {floor}"
    )
    if have < floor:
        return FAIL, f"{detail}; below the floor"
    if have < target and not str(ctx.meta.get("machine_share_note", "")).strip():
        return FAIL, f"{detail}; below target and machine_share_note is empty"
    return PASS, detail


def check_p5(ctx: Ctx) -> Result:
    """Real versus empty: the three gaps goldens tell evidence from none."""
    empty, err = _golden_json(ctx, "gaps_empty.json")
    if err:
        return FAIL, err
    if not any(
        str(r.get("status")).lower() == "missing" for r in _gap_rows(empty, ctx.key)
    ):
        return FAIL, "gaps_empty.json has no missing row"
    scaff, err = _golden_json(ctx, "gaps_scaffolded.json")
    if err:
        return FAIL, err
    for r in _gap_rows(scaff, ctx.key):
        conf = r.get("confidence")
        if (
            str(r.get("source")).lower() == "artifact"
            and conf is not None
            and conf >= EVIDENCED_CONFIDENCE
        ):
            return (
                FAIL,
                f"gaps_scaffolded.json: {r.get('article')} artifact row has confidence "
                f"{conf}; an unfilled scaffold must stay below the evidenced level "
                f"({EVIDENCED_CONFIDENCE})",
            )
    evid, err = _golden_json(ctx, "gaps_evidenced.json")
    if err:
        return FAIL, err
    for r in _gap_rows(evid, ctx.key):
        conf = r.get("confidence")
        if (
            isinstance(conf, (int, float)) and math.isclose(conf, EVIDENCED_CONFIDENCE)
        ) or (str(r.get("status")).lower() == "met" and r.get("corroborated") is True):
            return PASS, "empty, scaffolded and evidenced goldens differ as required"
    return (
        FAIL,
        "gaps_evidenced.json has no row at confidence 0.6 or met and corroborated",
    )


def check_p6(ctx: Ctx) -> Result:
    """Verdict words: every row status in the three gaps goldens is a known word."""
    total = 0
    for stem in GAP_GOLDENS:
        data, err = _golden_json(ctx, f"{stem}.json")
        if err:
            return FAIL, err
        for r in _gap_rows(data, ctx.key):
            total += 1
            word = str(r.get("status")).lower()
            if word not in VERDICT_WORDS:
                return FAIL, f"{stem}.json: {r.get('article')} has status {word!r}"
    return PASS, f"{total} row status(es) use the four verdict words"


def check_p8(ctx: Ctx) -> Result:
    """Gate: the empty gate golden exits 1 and names requirement ids."""
    path = ctx.golden / "gate_empty.txt"
    if not path.is_file():
        return FAIL, "no golden gate_empty.txt"
    text = path.read_text(encoding="utf-8")
    if not re.match(r"exit=1(?!\d)", text):
        return FAIL, "gate_empty.txt does not start with exit=1"
    if f"{ctx.key}:" not in text:
        return FAIL, f"gate_empty.txt lists no {ctx.key}: requirement id"
    return PASS, "gate fails with exit=1 and lists requirement ids"


def check_p9(ctx: Ctx) -> Result:
    """CI reports: three goldens; the JUnit file has this pack's classname."""
    absent = [n for n in REPORT_GOLDENS if not (ctx.golden / n).is_file()]
    if absent:
        return FAIL, f"no golden {', '.join(absent)}"
    junit = (ctx.golden / REPORT_GOLDENS[0]).read_text(encoding="utf-8")
    if f'classname="opencomplai.{ctx.key}"' not in junit:
        return FAIL, f"{REPORT_GOLDENS[0]} has no classname opencomplai.{ctx.key}"
    return PASS, "junit, sarif and summary goldens present"


def check_p10(ctx: Ctx) -> Result:
    """Templates: each machine or hybrid row maps to a template file."""
    wanted = sorted(
        rid
        for rid, r in ctx.rows.items()
        if isinstance(r, dict) and r.get("evidence_class") in ("machine", "hybrid")
    )
    if not wanted:
        return PASS, "no machine or hybrid rows"
    path = ctx.pack_path / "templates" / "template_map.json"
    if not path.is_file():
        return FAIL, "no templates/template_map.json"
    tmap = _read(path)
    if not isinstance(tmap, dict):
        return FAIL, "template_map.json is not an object"
    for rid in wanted:
        entry = tmap.get(rid)
        if not isinstance(entry, dict):
            return FAIL, f"{rid}: not in template_map.json"
        name = entry.get("file")
        if not isinstance(name, str) or not (path.parent / name).is_file():
            return FAIL, f"{rid}: template file {name!r} not found"
    return PASS, f"{len(wanted)} row(s) have template files"


def check_p11(ctx: Ctx) -> Result:
    """Scaffolds: one to four documents that resolve, carry the marker, name a probe."""
    path = ctx.pack_path / "scaffolds" / "scaffolds.json"
    if not path.is_file():
        return FAIL, "no scaffolds/scaffolds.json"
    docs = _read(path)
    if not isinstance(docs, dict) or not 1 <= len(docs) <= MAX_SCAFFOLDS:
        return FAIL, f"scaffolds.json needs one to {MAX_SCAFFOLDS} documents"
    for doc, entry in docs.items():
        try:
            text = pack_scaffolds.scaffold_text(ctx.key, doc)
        except (KeyError, ValueError, OSError) as exc:
            return FAIL, f"{doc}: does not resolve: {exc}"
        if "_fill in_" not in text:
            return FAIL, f"{doc}: no _fill in_ marker"
        probe = entry.get("probe") if isinstance(entry, dict) else None
        if not isinstance(probe, str) or not probe_exists(probe):
            return FAIL, f"{doc}: probe {probe!r} not accepted"
    return PASS, f"{len(docs)} scaffold document(s) resolve"


def check_p12(ctx: Ctx) -> Result:
    """Timeline: loads; a `none` timeline has a real reason and no dated notes."""
    regulatory_timeline.load_pack_timeline.cache_clear()
    try:
        regulatory_timeline.load_pack_timeline(ctx.key)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return FAIL, f"timeline does not load: {exc}"
    if ctx.meta.get("timeline") != "none":
        return PASS, f"timeline mode {ctx.meta.get('timeline')}"
    reason = str(ctx.meta.get("timeline_reason", "")).strip()
    if not reason or reason.lower() == PLACEHOLDER_REASON:
        return FAIL, "timeline none needs a timeline_reason other than the placeholder"
    for rid, r in ctx.rows.items():
        note = r.get("note") if isinstance(r, dict) else None
        if isinstance(note, str) and DATE_RE.search(note):
            return FAIL, f"{rid}: note holds a date"
    return PASS, "timeline none with a stated reason and no dated notes"


def check_p13(ctx: Ctx) -> Result:
    """Report: the report section golden shows the evidence class."""
    path = ctx.golden / "report_section.html"
    if not path.is_file():
        return FAIL, "no golden report_section.html"
    if "Evidence class" not in path.read_text(encoding="utf-8"):
        return FAIL, "report_section.html lacks 'Evidence class'"
    return PASS, "report section shows the evidence class"


def check_p14(ctx: Ctx) -> Result:
    """Goldens: every expected golden and fixture entry exists."""
    names = [f"{s}{e}" for s in GAP_GOLDENS for e in (".json", ".txt")]
    names += ["gate_empty.txt", *REPORT_GOLDENS, "report_section.html"]
    absent = [f"golden {n}" for n in names if not (ctx.golden / n).is_file()]
    absent += [
        f"fixture {n}" for n in FIXTURE_ENTRIES if not (ctx.fixtures / n).exists()
    ]
    if absent:
        return FAIL, f"missing: {', '.join(absent)}"
    return PASS, f"{len(names)} goldens and {len(FIXTURE_ENTRIES)} fixture entries"


def check_p15(ctx: Ctx) -> Result:
    """Docs page: it exists, its row table is current, and with --gate it is in the nav."""
    page = pack_doc.docs_page(ctx.key, ctx.meta)
    if not (pack_doc.DOCS_SRC / page).is_file():
        return FAIL, f"no docs page docs/src/{page}"
    problems = pack_doc.check(ctx.key)
    if problems:
        return FAIL, problems[0]
    if ctx.gate:
        try:
            nav = MKDOCS.read_text(encoding="utf-8")
        except OSError:
            return FAIL, "docs/mkdocs.yml unreadable"
        if page not in nav:
            return FAIL, f"{page} is not in docs/mkdocs.yml"
        return PASS, f"docs/src/{page} current and in docs/mkdocs.yml"
    return PASS, f"docs/src/{page} current"


_DECIDED: dict[int, Callable[[Ctx], Result]] = {
    1: check_p1,
    2: check_p2,
    3: check_p3,
    4: check_p4,
    5: check_p5,
    6: check_p6,
    7: check_p7,
    8: check_p8,
    9: check_p9,
    10: check_p10,
    11: check_p11,
    12: check_p12,
    13: check_p13,
    14: check_p14,
    15: check_p15,
}
CHECKS: dict[str, Callable[[Ctx], Result]] = {
    f"P{n}": _DECIDED[n] for n in range(1, 16)
}


def run(key: str, gate: bool = False) -> dict[str, Any]:
    ctx = load_ctx(key, gate)
    counts = _counts(ctx)
    caps: dict[str, dict[str, str]] = {}
    for name, fn in CHECKS.items():
        try:
            result, detail = fn(ctx)
        except (KeyError, TypeError, ValueError, AttributeError, OSError) as exc:
            result, detail = FAIL, f"data not readable: {exc!r}"
        caps[name] = {"result": result, "detail": detail}
    return {
        "key": key,
        "rows": len(ctx.rows),
        "machine": counts["machine"],
        "hybrid": counts["hybrid"],
        "organisational": counts["organisational"],
        "capabilities": caps,
    }


def _all_keys() -> list[str]:
    return [m["id"] for m in pack_registry.discover_packs() if m["id"] != EU_KEY]


def _text(report: dict[str, Any]) -> str:
    return "\n".join(
        f"{n} {c['result']} {c['detail']}" for n, c in report["capabilities"].items()
    )


def _clean(report: dict[str, Any]) -> bool:
    return all(c["result"] == PASS for c in report["capabilities"].values())


def write_status(key: str, report: dict[str, Any]) -> str | None:
    """Set `status` in pack.json from the report; the new value, or None if unchanged."""
    if key == EU_KEY:
        return None
    path = pack_registry.pack_dir(key) / pack_registry.PACK_FILE
    meta = _read(path)
    if _clean(report):
        new = "evaluated"
    elif meta.get("status") == "evaluated":
        new = "derived" if key == NIST_KEY else "attestation-led"
    else:
        return None
    if meta.get("status") == new:
        return None
    meta["status"] = new
    path.write_text(packfmt.dump(meta), encoding="utf-8", newline="")
    return new


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("key", nargs="?", help="pack key, e.g. GDPR")
    ap.add_argument("--all", action="store_true", help="every non-EU pack")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--gate", action="store_true", help="P15 also needs the nav entry")
    ap.add_argument(
        "--write-status", action="store_true", help="write the derived status"
    )
    args = ap.parse_args(argv)
    if args.all:
        keys = _all_keys()
    elif args.key:
        keys = [args.key]
    else:
        ap.error("give a pack key or --all")
    if args.key == EU_KEY and not args.all:
        print(
            json.dumps({"key": EU_KEY, "reference_pack": True})
            if args.json
            else "reference pack"
        )
        return 0
    if (
        not args.all
        and not (pack_registry.pack_dir(args.key) / pack_registry.PACK_FILE).is_file()
    ):
        print(f"unknown pack {args.key}", file=sys.stderr)
        return 2
    reports = [run(k, args.gate) for k in keys]
    if args.write_status:
        for rep in reports:
            new = write_status(rep["key"], rep)
            if new:
                print(f"{rep['key']}: status set to {new}", file=sys.stderr)
    if args.json:
        print(json.dumps(reports if args.all else reports[0], indent=2))
    else:
        for rep in reports:
            if args.all:
                print(f"== {rep['key']}")
            print(_text(rep))
    return 0 if all(_clean(r) for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
