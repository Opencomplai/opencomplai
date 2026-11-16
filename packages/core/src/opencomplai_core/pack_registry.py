"""Discovery of framework packs: one directory per pack under `packs/`.

Each pack directory holds a `pack.json` with the pack's metadata. This module
reads those files and nothing else; `frameworks.py` turns them into registry
entries. Standard library only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PACKS_DIR = Path(__file__).resolve().parent / "packs"
PACK_FILE = "pack.json"

REQUIRED_FIELDS = (
    "id",
    "order",
    "kind",
    "name",
    "short_name",
    "status",
    "disclaimer_ref",
    "requirements",
    "data_files",
    "legacy_file",
    "copyright",
    "row_count",
    "target_machine_share",
    "timeline",
    "catalogue",
)
KINDS = ("native", "derived", "hybrid")


def pack_dir(key: str) -> Path:
    return PACKS_DIR / key


def load_pack_meta(key: str) -> dict[str, Any]:
    """Read `packs/<key>/pack.json`; ValueError naming the file when it is
    unreadable, lacks a field, or its `id` differs from the directory name."""
    path = pack_dir(key) / PACK_FILE
    try:
        with path.open(encoding="utf-8") as handle:
            meta = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{path}: cannot read pack metadata: {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: pack metadata must be a JSON object")
    missing = [name for name in REQUIRED_FIELDS if name not in meta]
    if missing:
        raise ValueError(f"{path}: missing field(s) {', '.join(missing)}")
    if meta["id"] != key:
        raise ValueError(
            f"{path}: id {meta['id']!r} differs from directory name {key!r}"
        )
    if meta["kind"] not in KINDS:
        raise ValueError(f"{path}: kind must be one of {', '.join(KINDS)}")
    return meta


def discover_packs() -> list[dict[str, Any]]:
    """Metadata of every pack directory, sorted by `order` (then by key)."""
    if not PACKS_DIR.is_dir():
        return []
    metas = [
        load_pack_meta(entry.name)
        for entry in sorted(PACKS_DIR.iterdir())
        if entry.is_dir() and (entry / PACK_FILE).is_file()
    ]
    return sorted(metas, key=lambda meta: (meta["order"], meta["id"]))


def pack_label(meta: dict[str, Any]) -> str:
    """`label` when present, else `<name> (<status>, <caveat>)`."""
    if meta.get("label"):
        return str(meta["label"])
    return f"{meta['name']} ({meta['status']}, {meta['caveat']})"


def pack_file(key: str, name: str) -> Path | None:
    """The path of `name` inside the pack directory, or None when absent."""
    path = pack_dir(key) / name
    return path if path.is_file() else None
