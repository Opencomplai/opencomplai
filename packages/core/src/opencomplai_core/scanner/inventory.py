"""Repository inventory — `.ocignore`-driven file enumeration."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path

from opencomplai_core.models import EvidenceScope
from opencomplai_core.scanner.feature_types import ScanProgressCallback

SCOPE_PATTERNS: list[tuple[str, EvidenceScope]] = [
    ("test", EvidenceScope.TEST),
    ("tests", EvidenceScope.TEST),
    ("spec", EvidenceScope.TEST),
    ("docs", EvidenceScope.DOCS),
    ("doc", EvidenceScope.DOCS),
    ("generated", EvidenceScope.GENERATED),
    ("vendor", EvidenceScope.VENDOR),
    ("dev", EvidenceScope.DEV),
]

LANGUAGE_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cs": "csharp",
    ".ipynb": "notebook",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".txt": "text",
    ".md": "markdown",
    ".lock": "lockfile",
}

MODEL_EXTENSIONS = {
    ".onnx",
    ".safetensors",
    ".gguf",
    ".pt",
    ".pth",
    ".pkl",
    ".joblib",
    ".h5",
    ".tflite",
    ".mlmodel",
    ".faiss",
    ".npy",
    ".npz",
}


@dataclass
class InventoryLimits:
    max_files: int = 0
    max_bytes_per_file: int = 0
    max_total_bytes: int = 0
    skip_binary: bool = False
    max_symlink_depth: int = 5
    max_notebook_cells: int = 500


@dataclass
class InventoryEntry:
    path: str
    rel_path: str
    language: str
    scope: EvidenceScope
    size_bytes: int
    is_binary: bool = False


@dataclass
class RepoInventory:
    repo_root: Path
    entries: list[InventoryEntry] = field(default_factory=list)
    skipped_paths: list[str] = field(default_factory=list)
    skip_reasons: dict[str, int] = field(default_factory=dict)
    limits_hit: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limits: InventoryLimits = field(default_factory=InventoryLimits)


def _record_skip(inventory: RepoInventory, rel: str, reason: str) -> None:
    inventory.skipped_paths.append(rel)
    inventory.skip_reasons[reason] = inventory.skip_reasons.get(reason, 0) + 1


def _is_ignored(rel: str, patterns: list[str]) -> bool:
    norm = rel.replace("\\", "/")
    base = os.path.basename(norm)
    for pat in patterns:
        if fnmatch.fnmatch(norm, pat) or fnmatch.fnmatch(base, pat):
            return True
        if pat.endswith("/"):
            prefix = pat.rstrip("/")
            if norm == prefix or norm.startswith(prefix + "/"):
                return True
    return False


def _classify_scope(rel_path: str) -> EvidenceScope:
    lower = rel_path.lower().replace("\\", "/")
    parts = lower.split("/")
    for part in parts:
        for key, scope in SCOPE_PATTERNS:
            if key in part:
                return scope
    return EvidenceScope.PROD


def _is_binary_sample(path: Path, size: int) -> bool:
    if size == 0:
        return False
    try:
        with path.open("rb") as f:
            chunk = f.read(8192)
        if b"\x00" in chunk:
            return True
    except OSError:
        return True
    return False


def _resolve_path(
    path: Path, repo_root: Path, depth: int, limits: InventoryLimits
) -> Path | None:
    if limits.max_symlink_depth > 0 and depth > limits.max_symlink_depth:
        return None
    try:
        resolved = path.resolve(strict=False)
    except OSError:
        return None
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        return None
    return resolved


def build_repo_inventory(
    repo_root: Path,
    limits: InventoryLimits | None = None,
    extra_excludes: frozenset[str] | None = None,
    *,
    ignore_patterns: list[str] | None = None,
    progress_cb: ScanProgressCallback | None = None,
) -> RepoInventory:
    limits = limits or InventoryLimits()
    patterns = list(ignore_patterns or [])
    if extra_excludes:
        for name in extra_excludes:
            pat = name if name.endswith("/") else name
            if pat not in patterns:
                patterns.append(pat)

    repo_root = repo_root.resolve()
    inventory = RepoInventory(repo_root=repo_root, limits=limits)
    total_bytes = 0

    if progress_cb:
        progress_cb.on_phase("inventory", 0)

    for dirpath, dirnames, filenames in os.walk(repo_root, followlinks=False):
        rel_dir = str(Path(dirpath).relative_to(repo_root)).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""

        dirnames[:] = [
            d
            for d in dirnames
            if not _is_ignored(f"{rel_dir}/{d}".strip("/"), patterns)
        ]

        for name in filenames:
            if limits.max_files > 0 and len(inventory.entries) >= limits.max_files:
                inventory.limits_hit.append("max_files")
                return inventory

            rel = f"{rel_dir}/{name}".strip("/") if rel_dir else name
            if _is_ignored(rel, patterns):
                _record_skip(inventory, rel, "ignored")
                continue

            full = Path(dirpath) / name
            resolved = _resolve_path(full, repo_root, 0, limits)
            if resolved is None:
                _record_skip(inventory, rel, "traversal")
                inventory.warnings.append(f"path_traversal_blocked:{rel}")
                continue

            try:
                stat = resolved.stat()
            except OSError:
                _record_skip(inventory, rel, "unreadable")
                inventory.warnings.append(f"unreadable:{rel}")
                continue

            if (
                limits.max_bytes_per_file > 0
                and stat.st_size > limits.max_bytes_per_file
            ):
                _record_skip(inventory, rel, "oversized")
                inventory.limits_hit.append(f"max_bytes_per_file:{rel}")
                continue

            total_bytes += stat.st_size
            if limits.max_total_bytes > 0 and total_bytes > limits.max_total_bytes:
                inventory.limits_hit.append("max_total_bytes")
                return inventory

            ext = resolved.suffix.lower()
            language = LANGUAGE_BY_EXT.get(ext, "unknown")
            is_binary = _is_binary_sample(resolved, stat.st_size)
            if limits.skip_binary and is_binary and ext not in MODEL_EXTENSIONS:
                _record_skip(inventory, rel, "binary")
                continue

            inventory.entries.append(
                InventoryEntry(
                    path=str(resolved),
                    rel_path=rel.replace("\\", "/"),
                    language=language,
                    scope=_classify_scope(rel),
                    size_bytes=stat.st_size,
                    is_binary=is_binary,
                )
            )
            if progress_cb:
                progress_cb.on_step("inventory", len(inventory.entries), rel)

    if progress_cb:
        progress_cb.on_phase("inventory", len(inventory.entries))

    return inventory
