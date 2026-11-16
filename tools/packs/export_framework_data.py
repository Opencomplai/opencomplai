"""Turn the parity check into the framework data every surface reads.

Usage (from the repo root):
  uv run python tools/packs/export_framework_data.py --out PATH
  uv run python tools/packs/export_framework_data.py --check PATH
  uv run python tools/packs/export_framework_data.py --print standing-line
  uv run python tools/packs/export_framework_data.py --print status-table

`--out` writes sorted-key JSON; `--check` exits 1 with a diff when PATH is stale. The status
word comes from `parity_check` (pack.json `status`, kept by its --write-status); an `evaluated`
pack with a failing capability is reported as `attestation-led` (`derived` for NIST AI RMF).
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pack_doc
import parity_check
from opencomplai_core import pack_registry, pack_scaffolds
from opencomplai_core.frameworks import FRAMEWORKS, data_version, pack_requirements

CLASSES = ("machine", "hybrid", "organisational")


def _short_label(label: str) -> str:
    """The label without a trailing bracketed suffix (brackets may nest)."""
    text = label.rstrip()
    if not text.endswith(")"):
        return text
    depth = 0
    for i in range(len(text) - 1, -1, -1):
        depth += {")": 1, "(": -1}.get(text[i], 0)
        if depth == 0:
            return text[:i].rstrip() or text
    return text


def _eu_class(row: dict[str, Any]) -> str:
    """EU rows carry no evidence_class; derive it from their sources."""
    sources = [s for s in row.get("sources", []) if isinstance(s, dict)]
    if not any(s.get("kind") == "attestation" for s in sources):
        return "machine"
    if any(
        s.get("kind") != "attestation" and s.get("role") != "supporting"
        for s in sources
    ):
        return "hybrid"
    return "organisational"


def _rows(key: str) -> dict[str, dict[str, Any]]:
    data = pack_requirements(FRAMEWORKS[key]) or {}
    return {
        k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)
    }


def _framework(key: str) -> dict[str, Any]:
    meta = pack_registry.load_pack_meta(key)
    rows = _rows(key)
    if key == parity_check.EU_KEY:
        parity = dict.fromkeys(parity_check.CHECKS, True) | {"reference": True}
        classes = [_eu_class(r) for r in rows.values()]
        status = meta["status"]
    else:
        caps = parity_check.run(key)["capabilities"]
        parity = {n: c["result"] == parity_check.PASS for n, c in caps.items()}
        classes = [
            r.get("evidence_class")
            if r.get("evidence_class") in CLASSES
            else "organisational"
            for r in rows.values()
        ]
        status = meta["status"]
        if status == "evaluated" and not all(parity.values()):
            status = "derived" if key == parity_check.NIST_KEY else "attestation-led"
    page = pack_doc.docs_page(key, meta)
    return {
        "key": key,
        "slug": key.lower().replace("_", "-"),
        "label": _short_label(FRAMEWORKS[key].label),
        "status": status,
        "parity": parity,
        "rows": len(rows),
        **{c: classes.count(c) for c in CLASSES},
        "unreviewed_rows": sum(
            1 for r in rows.values() if r.get("needs_founder_review")
        ),
        "scaffolds": len(pack_scaffolds.list_scaffolds(key)),
        "has_timeline": meta["timeline"] != "none",
        "trackable": meta["catalogue"],
        "data_version": data_version(FRAMEWORKS[key]),
        "docs_page": page if (pack_doc.DOCS_SRC / page).is_file() else None,
    }


def build_framework_data() -> dict[str, Any]:
    return {"schema": 1, "frameworks": [_framework(k) for k in FRAMEWORKS]}


def standing_line(data: dict[str, Any]) -> str:
    groups: dict[str, list[str]] = {}
    for fw in data["frameworks"]:
        groups.setdefault(fw["status"], []).append(fw["label"])
    parts = [f"{status}: {', '.join(labels)}" for status, labels in groups.items()]
    return f"{len(data['frameworks'])} frameworks by status, {'; '.join(parts)}."


def status_table_md(data: dict[str, Any]) -> str:
    lines = [
        "| Framework | Key | Status | Rows | Checked from evidence | Unreviewed rows |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for fw in data["frameworks"]:
        lines.append(
            f"| {fw['label']} | {fw['key']} | {fw['status']} | {fw['rows']} "
            f"| {fw['machine'] + fw['hybrid']} | {fw['unreviewed_rows']} |"
        )
    return "\n".join(lines) + "\n"


def render(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    ap.add_argument("--out", help="write the JSON here")
    ap.add_argument("--check", help="exit 1 with a diff when this file is stale")
    ap.add_argument("--print", dest="show", choices=("standing-line", "status-table"))
    args = ap.parse_args(argv)
    if not (args.out or args.check or args.show):
        ap.error("give --out, --check or --print")
    data = build_framework_data()
    if args.out:
        Path(args.out).write_text(render(data), encoding="utf-8", newline="\n")
    if args.show == "standing-line":
        print(standing_line(data))
    elif args.show:
        print(status_table_md(data), end="")
    if args.check:
        want = render(data)
        try:
            have = Path(args.check).read_bytes().decode("utf-8").replace("\r\n", "\n")
        except OSError:
            have = ""
        if have != want:
            sys.stdout.writelines(
                difflib.unified_diff(
                    have.splitlines(True), want.splitlines(True), args.check, "current"
                )
            )
            print(f"{args.check} is stale; rerun with --out", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
