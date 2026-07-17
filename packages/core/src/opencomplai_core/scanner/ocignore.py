"""`.ocignore` — repo-owned scan inventory configuration."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from opencomplai_core.scanner.inventory import InventoryLimits

logger = logging.getLogger(__name__)

DEFAULT_OCIGNORE_TEMPLATE = """\
# Opencomplai scan configuration
# Pattern lines: ocignore subset v1 (fnmatch; use trailing / for directories)
# https://docs.opencomplai.com/getting-started/scanner#ocignore

[limits]
# Fail-closed defaults (0 = unlimited if you intentionally override)
max_files = 20000
max_bytes_per_file = 1048576
max_total_bytes = 209715200
skip_binary = false
# Symlinks are refused by default (allow_symlinks = false). Do not set
# max_symlink_depth = 0 expecting "refuse" — 0 means unlimited when links are allowed.
max_symlink_depth = 5
allow_symlinks = false
max_notebook_cells = 500

# --- Exclusions (edit freely) ---
.git/
node_modules/
.venv/
venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.tox/
dist/
build/
site/
docs/site/
.env
*.pem
*.key
*.pyc
htmlcov/
.coverage
.pnpm-store/
.idea/
.vscode/
.cursor/
compliance-artifact.json
system-manifest.json
docs/src/assets/js/checker-widget.js
docs/checker-widget/node_modules/
packages/cli/src/opencomplai_cli/data/checker-local.html
"""

_LIMIT_KEYS = frozenset(
    {
        "max_files",
        "max_bytes_per_file",
        "max_total_bytes",
        "skip_binary",
        "max_symlink_depth",
        "max_notebook_cells",
        "allow_symlinks",
    }
)

_INT_LIMIT_DEFAULTS: dict[str, int] = {
    "max_files": 20_000,
    "max_bytes_per_file": 1_048_576,
    "max_total_bytes": 209_715_200,
    "max_symlink_depth": 5,
    "max_notebook_cells": 500,
}


@dataclass
class OcignoreConfig:
    patterns: list[str] = field(default_factory=list)
    limits: InventoryLimits = field(default_factory=InventoryLimits)
    warnings: list[str] = field(default_factory=list)
    source_path: Path | None = None
    content_hash: str = "sha256:" + "0" * 64


def ocignore_content_hash(content: str) -> str:
    """SHA-256 of raw file bytes for cache invalidation."""
    return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"


def _strip_bom(text: str) -> str:
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def _parse_bool(value: str) -> bool | None:
    lower = value.strip().lower()
    if lower in ("true", "yes", "1", "on"):
        return True
    if lower in ("false", "no", "0", "off"):
        return False
    return None


def _parse_int(value: str) -> int | None:
    try:
        parsed = int(value.strip(), 10)
    except ValueError:
        return None
    if parsed < 0:
        return None
    return parsed


def _validate_pattern(line: str, line_no: int) -> tuple[str | None, str | None]:
    """Return (pattern, warning) for ocignore subset v1."""
    if line.startswith("!"):
        return None, f"line {line_no}: negation (!) not supported in ocignore v1"
    if "**" in line:
        return None, f"line {line_no}: '**' not supported in ocignore v1"
    if line.startswith("/"):
        return (
            None,
            f"line {line_no}: anchored paths (leading /) not supported in ocignore v1",
        )
    return line, None


def parse_ocignore(content: str, *, source: str = "<string>") -> OcignoreConfig:
    """Parse `.ocignore` content into patterns and limits."""
    content = _strip_bom(content).replace("\r\n", "\n").replace("\r", "\n")
    patterns: list[str] = []
    warnings: list[str] = []
    limits_raw: dict[str, str] = {}
    in_limits = False

    for line_no, raw in enumerate(content.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[limits]":
            in_limits = True
            continue
        if line.startswith("[") and line.endswith("]"):
            in_limits = False
            warnings.append(f"{source}:{line_no}: unknown section {line}")
            continue

        if in_limits:
            if "=" not in line:
                in_limits = False
            else:
                key, _, value = line.partition("=")
                key = key.strip().lower()
                value = value.strip()
                if key not in _LIMIT_KEYS:
                    warnings.append(f"{source}:{line_no}: unknown limit key '{key}'")
                else:
                    limits_raw[key] = value
                continue

        pat, warn = _validate_pattern(line, line_no)
        if warn:
            warnings.append(f"{source}:{warn}")
        if pat:
            patterns.append(pat)

    limits = _build_limits(limits_raw, source, warnings)
    for w in warnings:
        logger.warning(w)
    return OcignoreConfig(
        patterns=patterns,
        limits=limits,
        warnings=warnings,
        content_hash=ocignore_content_hash(content),
    )


def _build_limits(
    raw: dict[str, str], source: str, warnings: list[str]
) -> InventoryLimits:
    ints: dict[str, int] = dict(_INT_LIMIT_DEFAULTS)
    skip_binary = False
    allow_symlinks = False

    for key, value in raw.items():
        if key == "skip_binary":
            parsed = _parse_bool(value)
            if parsed is None:
                warnings.append(f"{source}: invalid skip_binary value '{value}'")
            else:
                skip_binary = parsed
            continue
        if key == "allow_symlinks":
            parsed = _parse_bool(value)
            if parsed is None:
                warnings.append(f"{source}: invalid allow_symlinks value '{value}'")
            else:
                allow_symlinks = parsed
            continue
        parsed = _parse_int(value)
        if parsed is None:
            warnings.append(f"{source}: invalid {key} value '{value}'")
        else:
            ints[key] = parsed

    return InventoryLimits(
        max_files=ints["max_files"],
        max_bytes_per_file=ints["max_bytes_per_file"],
        max_total_bytes=ints["max_total_bytes"],
        skip_binary=skip_binary,
        max_symlink_depth=ints["max_symlink_depth"],
        max_notebook_cells=ints["max_notebook_cells"],
        allow_symlinks=allow_symlinks,
    )


def resolve_ocignore_path(repo_root: Path, ocignore_path: Path | None = None) -> Path:
    """Resolve `.ocignore` path; must stay inside repo_root."""
    repo_root = repo_root.resolve()
    target = (ocignore_path or (repo_root / ".ocignore")).resolve()
    try:
        target.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(
            f"ocignore path must be inside repo_root ({repo_root}); got {target}"
        ) from exc
    return target


def load_ocignore(repo_root: Path, ocignore_path: Path | None = None) -> OcignoreConfig:
    """Load `.ocignore` read-only; missing file → empty patterns, default limits."""
    repo_root = repo_root.resolve()
    try:
        path = resolve_ocignore_path(repo_root, ocignore_path)
    except ValueError as exc:
        return OcignoreConfig(
            warnings=[str(exc)],
            limits=InventoryLimits(),
        )
    if not path.is_file():
        return OcignoreConfig(limits=InventoryLimits())
    text = path.read_text(encoding="utf-8", errors="replace")
    cfg = parse_ocignore(text, source=str(path))
    cfg.source_path = path
    return cfg


def _import_gitignore_lines(repo_root: Path) -> list[str]:
    gitignore = repo_root / ".gitignore"
    if not gitignore.is_file():
        return []
    lines: list[str] = []
    for raw in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def _dedupe_patterns(existing: list[str], extra: list[str]) -> list[str]:
    seen = set(existing)
    out = list(existing)
    for pat in extra:
        if pat not in seen:
            seen.add(pat)
            out.append(pat)
    return out


def ensure_ocignore(
    repo_root: Path,
    *,
    import_gitignore: bool = True,
    ocignore_path: Path | None = None,
) -> tuple[bool, Path]:
    """Create default `.ocignore` if missing (CLI bootstrap only).

    Returns (created, path). Does not overwrite an existing file.
    """
    repo_root = repo_root.resolve()
    path = resolve_ocignore_path(repo_root, ocignore_path)
    if path.exists():
        return False, path

    parsed = parse_ocignore(DEFAULT_OCIGNORE_TEMPLATE)
    patterns = list(parsed.patterns)
    if import_gitignore:
        patterns = _dedupe_patterns(patterns, _import_gitignore_lines(repo_root))

    header_end = DEFAULT_OCIGNORE_TEMPLATE.index("# --- Exclusions")
    header = DEFAULT_OCIGNORE_TEMPLATE[:header_end]
    content = (
        header + "# --- Exclusions (edit freely) ---\n" + "\n".join(patterns) + "\n"
    )

    try:
        path.write_text(content, encoding="utf-8")
    except OSError:
        return False, path
    return True, path


def config_dict_for_hash(
    patterns: list[str], limits: InventoryLimits, content_hash: str
) -> dict:
    """Canonical config for feature-cache hashing.

    Rules: sorted(patterns), limits as plain ints/bool, ocignore file SHA-256.
    """
    return {
        "patterns": sorted(patterns),
        "limits": {
            "max_files": limits.max_files,
            "max_bytes_per_file": limits.max_bytes_per_file,
            "max_total_bytes": limits.max_total_bytes,
            "skip_binary": limits.skip_binary,
            "max_symlink_depth": limits.max_symlink_depth,
            "max_notebook_cells": limits.max_notebook_cells,
            "allow_symlinks": limits.allow_symlinks,
        },
        "ocignore_hash": content_hash,
    }
