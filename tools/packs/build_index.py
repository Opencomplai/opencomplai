"""Write the index of all framework packs.

Usage (from the repo root):
  uv run python tools/packs/build_index.py          # rewrite the index
  uv run python tools/packs/build_index.py --check  # exit 1 when it is stale

The index is tools/packs/generated/frameworks.generated.json: one entry per pack,
in registry order. `build()` returns it as a dict, `render()` as the file text.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from opencomplai_core import frameworks
from opencomplai_core.pack_registry import discover_packs, pack_dir, pack_label

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "tools/packs/generated/frameworks.generated.json"
CLASSES = ("machine", "hybrid", "organisational")


def _scaffold_count(key: str) -> int:
    path = pack_dir(key) / "scaffolds" / "scaffolds.json"
    if not path.is_file():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data)


def _entry(meta: dict[str, Any]) -> dict[str, Any]:
    key = meta["id"]
    pack = frameworks.FRAMEWORKS[key]
    requirements = None
    counts = dict.fromkeys((*CLASSES, "unclassified"), 0)
    if pack.requirements is not None:
        requirements = os.path.relpath(pack.requirements, REPO).replace("\\", "/")
        rows = json.loads(pack.requirements.read_text(encoding="utf-8"))
        for row in rows.values():
            cls = row.get("evidence_class")
            counts[cls if cls in CLASSES else "unclassified"] += 1
        total = len(rows)
    else:
        total = meta["row_count"]
        counts["unclassified"] = total
    return {
        "key": key,
        "name": meta["name"],
        "short_name": meta["short_name"],
        "label": pack_label(meta),
        "status": meta["status"],
        "kind": meta["kind"],
        "copyright": meta["copyright"],
        "catalogue": bool(meta["catalogue"]),
        "legacy_file": meta["legacy_file"],
        "requirements": requirements,
        "rows": total,
        **counts,
        "target_machine_share": meta["target_machine_share"],
        "scaffolds": _scaffold_count(key),
        "has_timeline": meta["timeline"] != "none",
        "data_version": frameworks.data_version(pack),
    }


def build() -> dict[str, Any]:
    return {"packs": [_entry(meta) for meta in discover_packs()]}


def render() -> str:
    return json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="exit 1 when the index is stale"
    )
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        current = OUT.read_bytes().decode("utf-8") if OUT.is_file() else None
        if current != text:
            print(
                f"{OUT.relative_to(REPO).as_posix()} is stale; run tools/packs/build_index.py"
            )
            return 1
        print("pack index up to date")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(f"wrote {OUT.relative_to(REPO).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
