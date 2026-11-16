"""Read a returned framework-mapping review workbook into verdicts JSON.

Needs openpyxl for everything except a --selftest without the sent workbooks. Run from the repo root:

    uv run python tools/packs/read_verdicts.py <returned.xlsx> [--out verdicts.json] [--json]
    uv run python tools/packs/read_verdicts.py --count-reviewed <xlsx>
    uv run python tools/packs/read_verdicts.py --check-log <verdicts.json> <applied.json>
    uv run python tools/packs/read_verdicts.py --selftest

Read: prints a one-paragraph summary; writes the verdicts JSON to --out (or prints it
instead of the summary with --json). Never writes next to the workbook, never edits it.
--count-reviewed prints one integer: the rows with a reviewer verdict (a verdict word at
the start of the comment, with the verdict cell blank, counts too).
--check-log exits 1 when a row that needs a decision has no entry in the apply log.

Exit codes: 0 ok, 1 invalid (unreadable, unknown version, bad log, missing log entries),
2 not found.

Sheets and columns are matched by header text, never by letter: a verdict in column H
(v1 ISO 27090) or J (v4) reads the same. The version is detected by comparing the returned
cells outside the 'Reviewer ...' columns with every sent file (v1-v4 and wave2, read from
--sent-dir, default tools/packs/sent). v2 and v3 differ only in their creation time, so a file that
matches both is reported as v3 with v2 under version.identical.

Verdicts JSON (schema 1): source, version, totals, sheets (counts per review sheet), rows
(only rows with a verdict, a comment or a cell edit: sheet, id, excel_row, verdict
ok|change|drop|null, raw_verdict, comment, flags, stale, stale_columns, cell_edits),
findings (wave 2 'Reviewer decision' cells), structure (added_rows, deleted_rows,
sheets_missing, sheets_extra, info_sheet_changes), cell_edits (every edited cell outside
the reviewer columns, with link=true for the link columns).
Flags: no_comment (change/drop without a comment), verdict_in_comment, invalid_verdict,
comment_without_verdict, cell_edited. stale = the row changed between the returned
version and the latest sent one (v4 / wave2), or no longer exists there.

Apply log (what --check-log reads): {"entries": [{"sheet": "NIST AI RMF", "id": "GOVERN 1.6",
"status": "applied" | "declined" | "parked", "note": "..."}]} (a bare list works too). A row
needs an entry when its verdict is change or drop, its verdict is unclear (invalid, or a
comment with no verdict), one of its cells was edited, or it was added or deleted; so does
every filled Findings decision (sheet 'Findings for review', id = the topic).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import re
import sys
from collections import defaultdict
from functools import cache
from pathlib import Path

# The files sent to the reviewer, oldest first. Never edited.
FWMAP = Path(__file__).resolve().parents[2] / "tools/packs/sent"
BASELINES: dict = {}


def set_sent_dir(root: Path) -> None:
    global FWMAP
    FWMAP = root
    BASELINES.clear()
    BASELINES.update(
        {
            "v1": root / "review/framework-mapping-review.xlsx",
            "v2": root / "review/framework-mapping-review-v2.xlsx",
            "v3": root / "review/framework-mapping-review-v3.xlsx",
            "v4": root / "review/framework-mapping-review-v4.xlsx",
            "wave2": root / "wave2/review/framework-mapping-review-wave2.xlsx",
        }
    )


set_sent_dir(FWMAP)
LATEST = {"v1": "v4", "v2": "v4", "v3": "v4", "v4": "v4", "wave2": "wave2"}
VERDICTS = ("ok", "change", "drop")
STATUSES = ("applied", "declined", "parked")
SKIP_SHEETS = {"summary"}  # COUNTIF formulas, derived from the review sheets
MIN_MATCH = 0.8  # share of baseline cells that must be unchanged to name a version
LEAD = re.compile(r"^\W*(ok|change|drop)\b", re.IGNORECASE)
LINK = re.compile(r"^(eu ai act|nist ai rmf|iso 27001|iso 27090|iso 42001|soc 2)\b")


Workbook = load_workbook = None


def _need_openpyxl() -> None:
    global Workbook, load_workbook
    try:
        from openpyxl import Workbook, load_workbook
    except ImportError:
        sys.exit("openpyxl is missing: install it to read workbooks")


class InvalidError(Exception):
    pass


class NotFoundError(Exception):
    pass


# --- parsing ------------------------------------------------------------------------------


def norm(v) -> str:
    """Cell value as comparable text: CRLF to LF, trimmed, whole floats as ints."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).replace("\r\n", "\n").replace("\r", "\n").strip()


def hkey(v) -> str:
    return " ".join(norm(v).split()).casefold()


def parse(src) -> dict:
    """{'created': str, 'sheets': {casefolded title: sheet}}; src is a path or file object."""
    try:
        wb = load_workbook(src)
    except Exception as e:
        raise InvalidError(f"not a readable xlsx workbook ({type(e).__name__})") from e
    sheets = {}
    for ws in wb.worksheets:
        title = ws.title.strip()
        if title.casefold() in SKIP_SHEETS:
            continue
        cols, heads, hk = [], {}, []
        for c in ws[1]:
            h = hkey(c.value)
            if h:
                h = h if h not in heads else f"{h}#{c.column}"
                cols.append((c.column - 1, h))
                heads[h] = norm(c.value)
                hk.append(h)
        rev = {}
        for h in hk:
            if h.startswith("reviewer"):
                for role in ("verdict", "comment", "decision"):
                    if role in h:
                        rev.setdefault(role, h)
        rows, seen, empty = {}, defaultdict(int), 0
        for n, vals in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            cells = {h: norm(vals[i]) for i, h in cols if i < len(vals)}
            if not any(cells.values()):
                empty += 1
                if (
                    empty >= 200
                ):  # a formatted-to-the-bottom sheet must not run for a million rows
                    break
                continue
            empty = 0
            key = cells.get(hk[0], "") if hk else ""
            key = key or f"(row {n})"
            seen[key] += 1
            rows[key if seen[key] == 1 else f"{key}#{seen[key]}"] = {
                "row": n,
                "cells": cells,
            }
        sheets[title.casefold()] = {
            "title": title,
            "heads": heads,
            "hk": hk,
            "rev": rev,
            "rows": rows,
        }
    created = wb.properties.created
    return {"created": created.isoformat() if created else "", "sheets": sheets}


@cache
def baseline(label: str) -> dict:
    if not BASELINES[label].is_file():
        raise NotFoundError(str(BASELINES[label]))
    return parse(str(BASELINES[label]))


def diff(new: dict, old: dict) -> dict:
    """Differences outside the reviewer columns: cell edits, rows only in new (added), rows
    only in old (deleted), sheets on one side only. cost counts every difference in cells."""
    out = {
        "edits": [],
        "added": [],
        "deleted": [],
        "sheets_missing": [],
        "sheets_extra": [],
        "cost": 0,
        "cells": 0,
    }
    for sk, o in old["sheets"].items():
        width = sum(1 for h in o["hk"] if not h.startswith("reviewer"))
        out["cells"] += width * len(o["rows"])
        n = new["sheets"].get(sk)
        if n is None:
            out["sheets_missing"].append(o["title"])
            out["cost"] += width * len(o["rows"])
            continue
        cols = [
            h for h in dict.fromkeys(o["hk"] + n["hk"]) if not h.startswith("reviewer")
        ]
        for key, orow in o["rows"].items():
            nrow = n["rows"].get(key)
            if nrow is None:
                out["deleted"].append({"sheet": o["title"], "id": key})
                out["cost"] += width
                continue
            for h in cols:
                was, now = orow["cells"].get(h, ""), nrow["cells"].get(h, "")
                if was != now:
                    column = o["heads"].get(h) or n["heads"].get(h) or h
                    out["edits"].append(
                        {
                            "sheet": o["title"],
                            "id": key,
                            "excel_row": nrow["row"],
                            "column": column,
                            "link": bool(LINK.match(h)),
                            "was": was,
                            "now": now,
                        }
                    )
                    out["cost"] += 1
        for key in n["rows"]:
            if key not in o["rows"]:
                out["added"].append({"sheet": n["title"], "id": key})
                out["cost"] += width
    for sk, n in new["sheets"].items():
        if sk not in old["sheets"]:
            out["sheets_extra"].append(n["title"])
            out["cost"] += len(n["rows"]) * sum(
                1 for h in n["hk"] if not h.startswith("reviewer")
            )
    return out


def detect(ret: dict) -> dict:
    """Name the sent version a returned file derives from (fewest differing cells)."""
    scored = [
        (diff(ret, baseline(label))["cost"], label)
        for label in BASELINES
        if BASELINES[label].is_file()
    ]
    if not scored:
        raise NotFoundError(
            "none of the sent workbooks: "
            + ", ".join(str(p) for p in BASELINES.values())
        )
    low = min(cost for cost, _ in scored)
    tied = [
        label for cost, label in scored if cost == low
    ]  # BASELINES order: latest last
    d = diff(ret, baseline(tied[-1]))
    match = 1 - low / (d["cells"] or 1)
    if match < MIN_MATCH:
        raise InvalidError(
            f"matches none of the sent versions (closest {tied[-1]}: {match:.0%} of cells unchanged)"
        )
    by_date = [
        label
        for label in tied
        if ret["created"] and baseline(label)["created"] == ret["created"]
    ]
    label = by_date[0] if len(by_date) == 1 else tied[-1]
    return {
        "label": label,
        "identical": tied,
        "latest": LATEST[label],
        "differences": low,
        "match": round(match, 4),
        "candidates": {lab: cost for cost, lab in scored},
        "diff": d,
    }


@cache
def stale_map(label: str) -> dict:
    """{(sheet, id): [changed columns]} for rows that differ between version `label` and the latest."""
    latest = LATEST[label]
    if label == latest:
        return {}
    d = diff(baseline(label), baseline(latest))
    out: dict = defaultdict(list)
    for e in d["edits"]:
        out[(e["sheet"].casefold(), e["id"])].append(e["column"])
    for a in d["added"]:
        out[(a["sheet"].casefold(), a["id"])].append(f"row not in {latest}")
    return dict(out)


# --- reading verdicts -----------------------------------------------------------------------


def classify(cells: dict, vcol: str, ccol: str | None) -> tuple:
    """(verdict or None, raw verdict cell, comment, flags) for one review row."""
    raw, comment = cells.get(vcol, ""), cells.get(ccol, "") if ccol else ""
    m = (
        None if raw else LEAD.match(comment)
    )  # a verdict word leading the comment, verdict cell blank
    flags, verdict, rest = [], None, comment
    if raw:
        word = re.sub(r"\W+", " ", raw).strip().casefold()
        verdict = word if word in VERDICTS else None
        if verdict is None:
            flags.append("invalid_verdict")
    elif m:
        verdict, rest = m.group(1).casefold(), comment[m.end() :].strip(" \n-:,.;")
        flags.append("verdict_in_comment")
    elif comment:
        flags.append("comment_without_verdict")
    if verdict in ("change", "drop") and not rest:
        flags.append("no_comment")
    return verdict, raw, comment, flags


def count_reviewed(src) -> int:
    n = 0
    for s in parse(src)["sheets"].values():
        vcol = s["rev"].get("verdict")
        for row in s["rows"].values() if vcol else ():
            _, raw, _, flags = classify(row["cells"], vcol, s["rev"].get("comment"))
            n += bool(raw) or "verdict_in_comment" in flags
    return n


def read(src) -> dict:
    ret = parse(src)
    data = {k: s for k, s in ret["sheets"].items() if s["rev"]}
    if not data:
        raise InvalidError(
            "no sheet has a 'Reviewer verdict' or 'Reviewer decision' column"
        )
    ver = detect(ret)
    d = ver.pop("diff")
    stale = stale_map(ver["label"])
    edits = [e for e in d["edits"] if e["sheet"].casefold() in data]
    by_row = defaultdict(list)
    for e in edits:
        by_row[(e["sheet"].casefold(), e["id"])].append(e)
    added = [x for x in d["added"] if x["sheet"].casefold() in data]
    deleted = [x for x in d["deleted"] if x["sheet"].casefold() in data]
    structure = {
        "added_rows": added,
        "deleted_rows": deleted,
        "sheets_missing": d["sheets_missing"],
        "sheets_extra": d["sheets_extra"],
        # edits to the guide, changes and sources sheets: seen, never applied
        "info_sheet_changes": sum(len(d[k]) for k in ("edits", "added", "deleted"))
        - len(edits)
        - len(added)
        - len(deleted),
    }
    rows, findings, per_sheet = [], [], {}
    for sk, s in data.items():
        vcol, ccol, dcol = (s["rev"].get(k) for k in ("verdict", "comment", "decision"))
        for key, row in s["rows"].items():
            text = row["cells"].get(dcol, "") if dcol else ""
            if text:
                findings.append(
                    {
                        "sheet": s["title"],
                        "topic": key,
                        "excel_row": row["row"],
                        "decision": text,
                    }
                )
        if not vcol:
            continue
        c = per_sheet[s["title"]] = dict.fromkeys(
            ("rows", "reviewed", "ok", "change", "drop", "invalid"), 0
        )
        for key, row in s["rows"].items():
            verdict, raw, comment, flags = classify(row["cells"], vcol, ccol)
            c["rows"] += 1
            c["reviewed"] += bool(raw) or "verdict_in_comment" in flags
            if verdict:
                c[verdict] += 1
            c["invalid"] += "invalid_verdict" in flags
            row_edits = by_row.get((sk, key), [])
            if row_edits:
                flags.append("cell_edited")
            if not (raw or comment or row_edits):
                continue
            entry = {
                "sheet": s["title"],
                "id": key,
                "excel_row": row["row"],
                "verdict": verdict,
            }
            if raw:
                entry["raw_verdict"] = raw
            entry.update(comment=comment, flags=flags, stale=(sk, key) in stale)
            if entry["stale"]:
                entry["stale_columns"] = stale[(sk, key)]
            entry["cell_edits"] = row_edits
            rows.append(entry)
        c["not_reviewed"] = c["rows"] - c["reviewed"]
    totals = {
        k: sum(c[k] for c in per_sheet.values())
        for k in ("rows", "reviewed", "ok", "change", "drop", "invalid", "not_reviewed")
    }
    totals.update(
        cell_edits=len(edits),
        stale=sum(r["stale"] for r in rows),
        added_rows=len(structure["added_rows"]),
        deleted_rows=len(structure["deleted_rows"]),
        findings_decided=len(findings),
    )
    return {
        "schema": 1,
        "tool": "read_verdicts.py",
        "version": ver,
        "totals": totals,
        "sheets": per_sheet,
        "rows": rows,
        "findings": findings,
        "structure": structure,
        "cell_edits": edits,
    }


def summary(res: dict, name: str) -> str:
    t, v = res["totals"], res["version"]
    exact = "exact" if v["differences"] == 0 else f"{v['differences']} differing cells"
    also = (
        f" (same content as {', '.join(x for x in v['identical'] if x != v['label'])})"
        if len(v["identical"]) > 1
        else ""
    )
    return (
        f"read_verdicts: {name}: version {v['label']}{also}, {exact}; rows {t['rows']}; "
        f"reviewed {t['reviewed']} (ok {t['ok']}, change {t['change']}, drop {t['drop']}, invalid {t['invalid']}); "
        f"not reviewed {t['not_reviewed']}; cell edits {t['cell_edits']}; stale {t['stale']}; "
        f"added rows {t['added_rows']}; deleted rows {t['deleted_rows']}; findings decided {t['findings_decided']}"
    )


# --- apply log ------------------------------------------------------------------------------


def needed(verdicts: dict) -> dict:
    """{(sheet, id) casefolded: (sheet, id, why)} for everything that must be in the apply log."""
    need = {}

    def add(sheet, key, why):
        need.setdefault(
            (str(sheet).strip().casefold(), str(key).strip().casefold()),
            (sheet, key, why),
        )

    for r in verdicts["rows"]:
        if r["verdict"] in (None, "change", "drop") or r["cell_edits"]:
            add(
                r["sheet"],
                r["id"],
                r["verdict"] or ("cell edit" if r["cell_edits"] else "unclear verdict"),
            )
    for r in verdicts["structure"]["added_rows"]:
        add(r["sheet"], r["id"], "added row")
    for r in verdicts["structure"]["deleted_rows"]:
        add(r["sheet"], r["id"], "deleted row")
    for f in verdicts["findings"]:
        add(f["sheet"], f["topic"], "finding decision")
    return need


def check_log(verdicts: dict, applied) -> tuple[list[str], list[str], int]:
    """(problems, notes, rows that need an entry). Problems make --check-log exit 1."""
    if (
        not isinstance(verdicts, dict)
        or verdicts.get("schema") != 1
        or "rows" not in verdicts
    ):
        return ["not a verdicts JSON written by this tool (schema 1)"], [], 0
    entries = applied.get("entries") if isinstance(applied, dict) else applied
    if not isinstance(entries, list):
        return ['apply log must be a list of entries or {"entries": [...]}'], [], 0
    problems, notes, logged = [], [], {}
    for i, e in enumerate(entries):
        if not (
            isinstance(e, dict)
            and e.get("sheet")
            and e.get("id")
            and e.get("status") in STATUSES
        ):
            problems.append(
                f"entry {i}: needs sheet, id and status ({'/'.join(STATUSES)})"
            )
            continue
        logged[
            (str(e["sheet"]).strip().casefold(), str(e["id"]).strip().casefold())
        ] = e
    need = needed(verdicts)
    for key, (sheet, rid, why) in need.items():
        if key not in logged:
            problems.append(f"no log entry for {sheet} / {rid} ({why})")
    notes += [
        f"log entry for {e['sheet']} / {e['id']} matches no row that needs one"
        for k, e in logged.items()
        if k not in need
    ]
    return problems, notes, len(need)


def run_check_log(vpath: str, apath: str) -> int:
    docs = []
    for p in (vpath, apath):
        if not Path(p).is_file():
            raise NotFoundError(p)
        try:
            docs.append(json.loads(Path(p).read_text(encoding="utf-8")))
        except ValueError as e:
            raise InvalidError(f"{p} is not valid JSON ({e})") from e
    problems, notes, n = check_log(*docs)
    for line in notes:
        print(f"note: {line}", file=sys.stderr)
    for line in problems:
        print(f"MISSING: {line}", file=sys.stderr)
    print(f"check-log: {n} rows need an entry, {len(problems)} problems")
    return 1 if problems else 0


# --- self-test ------------------------------------------------------------------------------


def _bio(wb) -> io.BytesIO:
    b = io.BytesIO()
    wb.save(b)
    b.seek(0)
    return b


def _ids(wb, sheet) -> list[str]:
    return [norm(r[0].value) for r in wb[sheet].iter_rows(min_row=2) if r[0].value]


def _set(wb, sheet, key, header, value):
    ws = wb[sheet]
    col = next(c.column for c in ws[1] if hkey(c.value) == hkey(header))
    row = next(r for r in range(2, ws.max_row + 1) if norm(ws.cell(r, 1).value) == key)
    ws.cell(row, col).value = value


def _fill(wb, sheet, key, verdict=None, comment=None):
    if verdict is not None:
        _set(wb, sheet, key, "Reviewer verdict", verdict)
    if comment is not None:
        _set(wb, sheet, key, "Reviewer comment", comment)


def selftest() -> int:
    fails: list[str] = []

    def check(cond, msg):
        if not cond:
            fails.append(msg)

    def raw_read(label):
        return read(io.BytesIO(BASELINES[label].read_bytes()))

    # 1. Every sent file reads back as itself, untouched.
    expect_rows = {"v1": 168, "v2": 168, "v3": 168, "v4": 168, "wave2": 469}
    for label in BASELINES:
        r = raw_read(label)
        t = r["totals"]
        check(
            label in r["version"]["identical"] and r["version"]["differences"] == 0,
            f"{label}: version {r['version']['label']}/{r['version']['identical']}",
        )
        check(
            r["version"]["label"] == label, f"{label}: detected {r['version']['label']}"
        )
        check(
            t["rows"] == expect_rows[label] or label in ("v1", "v2", "v3"),
            f"{label}: rows {t['rows']}",
        )
        check(
            t["reviewed"] == 0
            and t["cell_edits"] == 0
            and t["not_reviewed"] == t["rows"],
            f"{label}: untouched file reads as reviewed or edited: {t}",
        )
        check(
            not r["rows"] and not r["findings"] and t["stale"] == 0,
            f"{label}: untouched file has rows or findings",
        )
    check(
        set(raw_read("v2")["version"]["identical"]) == {"v2", "v3"},
        "v2 and v3 must be reported as the same content",
    )

    # 2. A filled copy of the sent v4.
    wb = load_workbook(BASELINES["v4"])
    nist, i42, i27 = (_ids(wb, s) for s in ("NIST AI RMF", "ISO 42001", "ISO 27090"))
    _fill(wb, "NIST AI RMF", nist[0], "  OK ")  # padded, upper case
    _fill(wb, "NIST AI RMF", nist[1], "Change", "Add Art. 9")
    _fill(wb, "NIST AI RMF", nist[2], "change")  # no comment
    _fill(wb, "NIST AI RMF", nist[3], "DROP", "not relevant")
    _fill(wb, "NIST AI RMF", nist[4], "agree")  # not one of OK / change / drop
    _fill(
        wb, "ISO 42001", i42[0], None, "drop: does not apply"
    )  # verdict typed into the comment column
    _fill(wb, "ISO 42001", i42[1], None, "please check this one")  # comment, no verdict
    _fill(wb, "ISO 27090", i27[1], "ok", "fine, wording odd")
    _set(wb, "ISO 27090", i27[0], "EU AI Act", "Art. 99")  # link cell edited directly
    wb["ISO 27090"].delete_rows(wb["ISO 27090"].max_row)  # deleted row
    wb["NIST AI RMF"].append(["ZZ 9.9"])  # added row
    res = read(_bio(wb))
    t, rows = res["totals"], {(r["sheet"], r["id"]): r for r in res["rows"]}

    def flags(s, k):
        return rows[(s, k)]["flags"]

    check(
        res["version"]["label"] == "v4" and res["version"]["differences"] > 0,
        f"filled v4 detected as {res['version']['label']}",
    )
    check(
        rows[("NIST AI RMF", nist[0])]["verdict"] == "ok"
        and rows[("NIST AI RMF", nist[0])]["raw_verdict"] == "OK",
        "padded OK",
    )
    check(
        rows[("NIST AI RMF", nist[1])]["verdict"] == "change"
        and not flags("NIST AI RMF", nist[1]),
        "Change + comment",
    )
    check(
        flags("NIST AI RMF", nist[2]) == ["no_comment"],
        f"change without comment: {flags('NIST AI RMF', nist[2])}",
    )
    check(rows[("NIST AI RMF", nist[3])]["verdict"] == "drop", "upper-case DROP")
    check(
        rows[("NIST AI RMF", nist[4])]["verdict"] is None
        and "invalid_verdict" in flags("NIST AI RMF", nist[4]),
        "invalid verdict word",
    )
    r = rows[("ISO 42001", i42[0])]
    check(
        r["verdict"] == "drop" and r["flags"] == ["verdict_in_comment"],
        f"verdict in comment column: {r}",
    )
    check(
        rows[("ISO 42001", i42[1])]["flags"] == ["comment_without_verdict"]
        and rows[("ISO 42001", i42[1])]["verdict"] is None,
        "comment without verdict",
    )
    check(
        rows[("ISO 27090", i27[1])]["verdict"] == "ok"
        and not flags("ISO 27090", i27[1]),
        "ok with a comment",
    )
    edit = rows[("ISO 27090", i27[0])]["cell_edits"]
    check(
        len(edit) == 1
        and edit[0]["column"] == "EU AI Act"
        and edit[0]["link"]
        and edit[0]["now"] == "Art. 99",
        f"edited link cell: {edit}",
    )
    check(
        t["reviewed"] == 7
        and t["ok"] == 2
        and t["change"] == 2
        and t["drop"] == 2
        and t["invalid"] == 1,
        f"totals {t}",
    )
    check(
        t["cell_edits"] == 1
        and t["added_rows"] == 1
        and t["deleted_rows"] == 1
        and t["rows"] == 168,
        f"edits/rows {t}",
    )
    check(
        res["structure"]["added_rows"] == [{"sheet": "NIST AI RMF", "id": "ZZ 9.9"}],
        f"added row {res['structure']['added_rows']}",
    )
    check(
        res["structure"]["deleted_rows"] == [{"sheet": "ISO 27090", "id": i27[-1]}],
        f"deleted row {res['structure']['deleted_rows']}",
    )
    check(t["stale"] == 0, "v4 is the latest: nothing is stale")
    check(count_reviewed(_bio(wb)) == 7, "count_reviewed disagrees with read")

    # 3. The apply log.
    entries = [
        {"sheet": s, "id": k, "status": "parked"}
        for s, k in [
            ("NIST AI RMF", nist[1]),
            ("NIST AI RMF", nist[2]),
            ("NIST AI RMF", nist[3]),
            ("NIST AI RMF", nist[4]),
            ("iso 42001", i42[0]),
            ("ISO 42001", i42[1]),
            ("ISO 27090", i27[0]),
            ("NIST AI RMF", "ZZ 9.9"),
            ("ISO 27090", i27[-1]),
        ]
    ]
    problems, _, n = check_log(res, {"entries": entries})
    check(not problems and n == 9, f"complete log rejected: {problems} ({n} needed)")
    problems, _, _ = check_log(res, entries[:1] + entries[2:])
    check(
        len(problems) == 1 and nist[2] in problems[0], f"one missing entry: {problems}"
    )
    problems, _, _ = check_log(res, [dict(entries[0], status="done"), *entries[1:]])
    check(
        len(problems) == 2,
        f"bad status must be a problem and leave the row unlogged: {problems}",
    )

    # 4. v1 (verdict in column H of ISO 27090) and v3, whose rows moved on in v4.
    wb = load_workbook(BASELINES["v1"])
    _fill(wb, "ISO 27090", "6.5", "change", "x")
    _fill(wb, "NIST AI RMF", "MANAGE 1.3", "ok")
    _fill(wb, "NIST AI RMF", "GOVERN 1.1", "ok")
    res = read(_bio(wb))
    rows = {(r["sheet"], r["id"]): r for r in res["rows"]}
    check(
        res["version"]["label"] == "v1",
        f"filled v1 detected as {res['version']['label']}",
    )
    check(
        rows[("ISO 27090", "6.5")]["verdict"] == "change"
        and rows[("ISO 27090", "6.5")]["stale"],
        "v1 verdict in column H, stale",
    )
    check(
        rows[("NIST AI RMF", "MANAGE 1.3")]["stale"]
        and not rows[("NIST AI RMF", "GOVERN 1.1")]["stale"],
        "stale only where the row changed",
    )
    wb = load_workbook(BASELINES["v3"])
    _fill(wb, "ISO 27090", "6.9", "drop", "y")
    res = read(_bio(wb))
    check(
        res["version"]["label"] == "v3"
        and res["rows"][0]["stale"]
        and res["totals"]["stale"] == 1,
        f"filled v3: {res['version']['label']}, stale {res['totals']['stale']}",
    )

    # 5. A filled copy of the sent wave-2 file, including the Findings decision.
    wb = load_workbook(BASELINES["wave2"])
    dora, gdpr, topics = (
        _ids(wb, "DORA"),
        _ids(wb, "GDPR"),
        _ids(wb, "Findings for review"),
    )
    _fill(wb, "DORA", dora[0], "drop", "wrong article")
    _fill(wb, "GDPR", gdpr[0], " Ok")
    _set(wb, "NIS2", _ids(wb, "NIS2")[0], "ISO 27001", "A.99.99")
    _set(wb, "Findings for review", topics[0], "Reviewer decision", "keep Art. 10")
    res = read(_bio(wb))
    t = res["totals"]
    check(
        res["version"]["label"] == "wave2" and t["rows"] == 469,
        f"filled wave2: {res['version']['label']}, rows {t['rows']}",
    )
    check(
        t["reviewed"] == 2
        and t["drop"] == 1
        and t["ok"] == 1
        and t["cell_edits"] == 1
        and t["findings_decided"] == 1,
        f"wave2 totals {t}",
    )
    check(
        res["findings"][0]["topic"] == topics[0]
        and res["findings"][0]["decision"] == "keep Art. 10",
        f"findings {res['findings']}",
    )
    check(
        ("Findings for review", topics[0])
        in {(s, k) for s, k, _ in needed(res).values()},
        "a finding decision must need a log entry",
    )

    # 6. Bad input.
    other = Workbook()
    other.active.append(["Id", "Reviewer verdict"])
    other.active.append(["a", "ok"])
    for src, what in (
        (io.BytesIO(b"not a workbook"), "garbage"),
        (_bio(other), "unrelated workbook"),
    ):
        try:
            read(src)
            check(False, f"{what} was accepted")
        except InvalidError:
            pass

    # 7. The command line, on the real sent files.
    for label, rows_ in (("v4", 168), ("wave2", 469)):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main([str(BASELINES[label])])
        check(
            rc == 0
            and f"rows {rows_};" in out.getvalue()
            and f"not reviewed {rows_};" in out.getvalue()
            and "cell edits 0;" in out.getvalue(),
            f"cli {label}: rc {rc}: {out.getvalue()}",
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = main(["--count-reviewed", str(BASELINES[label])])
        check(
            rc == 0 and out.getvalue().strip() == "0",
            f"--count-reviewed {label}: rc {rc}: {out.getvalue()!r}",
        )
    with contextlib.redirect_stderr(io.StringIO()):
        check(main([str(FWMAP / "no-such.xlsx")]) == 2, "missing file must exit 2")
        check(
            main(["--check-log", str(FWMAP / "no-a.json"), str(FWMAP / "no-b.json")])
            == 2,
            "missing log must exit 2",
        )

    if fails:
        print("\n".join(f"FAIL: {f}" for f in fails), file=sys.stderr)
        return 1
    print("OK")
    return 0


# --- command line ---------------------------------------------------------------------------


class _Parser(argparse.ArgumentParser):
    def error(
        self, message
    ):  # usage errors are "invalid" (1); 2 is reserved for "not found"
        self.print_usage(sys.stderr)
        print(f"{self.prog}: {message}", file=sys.stderr)
        raise SystemExit(1)


def main(argv=None) -> int:
    ap = _Parser(description="Read a returned framework-mapping review workbook.")
    ap.add_argument("xlsx", nargs="?", help="returned workbook to read")
    ap.add_argument("--out", help="write the verdicts JSON here")
    ap.add_argument(
        "--json",
        action="store_true",
        help="print the verdicts JSON instead of the summary",
    )
    ap.add_argument(
        "--count-reviewed",
        metavar="XLSX",
        help="print the number of rows with a reviewer verdict",
    )
    ap.add_argument(
        "--check-log",
        nargs=2,
        metavar=("VERDICTS", "APPLIED"),
        help="check an apply log against a verdicts JSON",
    )
    ap.add_argument(
        "--selftest", action="store_true", help="run the built-in checks; prints OK"
    )
    ap.add_argument(
        "--sent-dir",
        default=str(FWMAP),
        help="folder with the sent review workbooks (default tools/packs/sent)",
    )
    a = ap.parse_args(argv)
    set_sent_dir(Path(a.sent_dir))
    try:
        if a.selftest:
            if not Path(a.sent_dir).is_dir():
                print("sent workbooks not present")
                return 0
            _need_openpyxl()
            return selftest()
        _need_openpyxl()
        if a.check_log:
            return run_check_log(*a.check_log)
        path = a.count_reviewed or a.xlsx
        if not path:
            ap.error("give a workbook, --count-reviewed, --check-log or --selftest")
        if not Path(path).is_file():
            raise NotFoundError(path)
        data = Path(path).read_bytes()
        if a.count_reviewed:
            print(count_reviewed(io.BytesIO(data)))
            return 0
        res = read(io.BytesIO(data))
        res["source"] = {
            "file": Path(path).name,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        text = json.dumps(res, indent=2, ensure_ascii=False) + "\n"
        if a.out:
            with open(a.out, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        line = summary(res, Path(path).name)
        if a.json:
            print(text, end="")
            print(line, file=sys.stderr)
        else:
            print(line)
        return 0
    except NotFoundError as e:
        print(f"not found: {e}", file=sys.stderr)
        return 2
    except InvalidError as e:
        print(f"invalid: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
