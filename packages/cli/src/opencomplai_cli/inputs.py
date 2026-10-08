"""Tolerant readers for files the CLI takes as input.

Stdlib only at import time; `load_manifest` imports the model lazily.
"""

from __future__ import annotations

import codecs
import json
import locale
import sys
from pathlib import Path
from typing import Any


def read_json_file(path: Path) -> Any:
    """Parse a JSON file written by any shell redirect, unwrapping the output
    envelope (`payload` + `tool_version`) that `-o json` prints.

    Windows PowerShell 5.1 `>` writes UTF-16LE with a BOM, so a UTF-16 BOM
    selects UTF-16; anything else is UTF-8 (BOM optional), falling back to the
    locale encoding (a cmd.exe or Git Bash `>` redirect writes cp1252).
    Raises ValueError when the file is empty or not JSON.
    """
    data = Path(path).read_bytes()
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        text = data.decode("utf-16")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode(locale.getpreferredencoding(False))
    try:
        raw = json.loads(text)
    except ValueError as e:  # JSONDecodeError subclasses ValueError
        raise ValueError(f"{path}: not valid JSON: {e}") from e
    if isinstance(raw, dict) and "payload" in raw and "tool_version" in raw:
        raw = raw["payload"]
    return raw


def load_manifest(path: Path, strict: bool = False):
    """Load a system manifest. Unknown top-level keys are dropped by the model,
    so name them on stderr; under `strict` that is an error (exit 2).
    Validation errors propagate to the caller unchanged."""
    from opencomplai_core.models import SystemManifest, unknown_manifest_keys

    from opencomplai_cli.commands.portfolio import reject_multi_system

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if (msg := reject_multi_system(raw)) is not None:
        raise ValueError(msg)
    manifest = SystemManifest.model_validate(raw)
    unknown = unknown_manifest_keys(raw) if isinstance(raw, dict) else []
    if unknown:
        keys = ", ".join(unknown)
        if strict:
            print(f"Error: unknown manifest key(s): {keys}", file=sys.stderr)
            sys.exit(2)
        print(f"Warning: unknown manifest key(s): {keys} (ignored)", file=sys.stderr)
    return manifest
