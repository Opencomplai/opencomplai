"""`check` over several manifests: one single-system run each, plus an
unsigned portfolio summary beside the per-system output directories.

`main.py` imports nothing from here at module load that could cycle: the
console is obtained lazily, as in `commands/halt.py`.
"""

from __future__ import annotations

import glob
import hashlib
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path("system-manifest.json")
MULTI_SYSTEM_MESSAGE = "one manifest describes one system; pass one -m per system"


def _consoles():
    from opencomplai_cli import main as _main

    return _main.console, _main.err_console, _main.OutputFormat


def _fail(message: str) -> None:
    _consoles()[1].print(f"[red]Error:[/red] {message}")
    sys.exit(2)


def expand_manifest_args(values: list[Path] | None) -> list[Path]:
    """Existing files stay; other values with glob characters are expanded
    here (Windows shells do not). A plain missing file passes through so the
    single-manifest "not found" error is unchanged."""
    if not values:
        return [DEFAULT_MANIFEST]
    out: list[Path] = []
    seen: set[Path] = set()
    for value in values:
        text = str(value)
        if value.is_file() or not any(c in text for c in "*?["):
            found = [value]
        else:
            found = [Path(p) for p in sorted(glob.glob(text, recursive=True))]
            if not found:
                _fail(f"manifest pattern matched no files: {text}")
        for path in found:
            key = path.resolve()
            if key not in seen:
                seen.add(key)
                out.append(path)
    return out


def reject_multi_system(raw: object) -> str | None:
    if isinstance(raw, list) or (isinstance(raw, dict) and "systems" in raw):
        return MULTI_SYSTEM_MESSAGE
    return None


def safe_dir_name(system_id: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]", "_", system_id)
    return "_" if name in ("", ".", "..") else name


def _read_raw(path: Path) -> object:
    from opencomplai_cli.inputs import read_json_file

    try:
        return read_json_file(path)
    except Exception:  # the child run reports the real error
        return None


def _system_id(path: Path) -> str:
    raw = _read_raw(path)
    sid = raw.get("system_id") if isinstance(raw, dict) else None
    return sid if isinstance(sid, str) and sid else path.stem


def _exit_code(exc: SystemExit) -> int:
    if exc.code is None:
        return 0
    return exc.code if isinstance(exc.code, int) else 1


def coerce_path_params(params: dict, command: Any) -> dict:
    """Copy of `params` with str values of click `Path` options turned into
    `Path`, as the single-system run expects them."""
    path_names = {p.name for p in command.params if p.type.name == "path" and p.name}
    return {
        k: Path(v) if k in path_names and isinstance(v, str) else v
        for k, v in params.items()
    }


def run_portfolio(
    ctx_params: dict,
    manifests: list[Path],
    invoke: Callable[..., None],
    command: Any,
) -> int:
    """Run `invoke(**params)` once per manifest and write the summary.
    Returns the worst (numeric maximum) child exit code."""
    for m in manifests:
        if (msg := reject_multi_system(_read_raw(m))) is not None:
            _fail(f"{m}: {msg}")
    ids = [_system_id(m) for m in manifests]
    names = [safe_dir_name(sid) for sid in ids]
    if len(set(names)) != len(names):
        _fail("two manifests resolve to the same system_id or system directory")

    base = Path(ctx_params.get("output_dir") or ".")
    entries: list[dict] = []
    for manifest, sid in zip(manifests, ids, strict=True):
        sys_dir = base / safe_dir_name(sid)
        params = {
            **coerce_path_params(ctx_params, command),
            "manifest_files": [manifest],
            "output_dir": sys_dir,
            "output": _consoles()[2].human,
        }
        try:
            invoke(**params)
            code = 0
        except SystemExit as e:
            code = _exit_code(e)
        artifact = sys_dir / "compliance-artifact.json"
        result, failed, rel, digest = (
            "validation_fail" if code == 2 else "unknown",
            [],
            None,
            None,
        )
        if artifact.is_file():
            data = artifact.read_bytes()
            doc = json.loads(data)
            result = doc.get("result", result)
            failed = doc.get("failed_controls", [])
            rel = f"{safe_dir_name(sid)}/compliance-artifact.json"
            digest = hashlib.sha256(data).hexdigest()
        entries.append(
            {
                "system_id": sid,
                "manifest": str(manifest),
                "exit_code": code,
                "result": result,
                "failed_controls": failed,
                "artifact": rel,
                "artifact_sha256": digest,
            }
        )
    worst = max(e["exit_code"] for e in entries)
    path = write_summary(base, entries, worst)

    out = ctx_params["output"]
    console = _consoles()[0]
    if getattr(out, "value", out) == "json":
        console.print_json(path.read_text())
    else:
        console.print("\n[bold]Portfolio[/bold]")
        for e in sorted(entries, key=lambda e: e["system_id"]):
            console.print(f"  {e['system_id']}: {e['result']} (exit {e['exit_code']})")
        console.print(f"[dim]Summary written to {path} (unsigned)[/dim]")
    return worst


def write_summary(base: Path, entries: list[dict], worst: int) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    path = base / "portfolio-summary.json"
    doc = {
        "kind": "portfolio_summary",
        "schema_version": "1",
        "signed": False,
        "worst_exit_code": worst,
        "systems": sorted(entries, key=lambda e: e["system_id"]),
    }
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    return path
