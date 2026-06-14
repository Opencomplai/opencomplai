"""Manifest and lockfile package extraction."""

from __future__ import annotations

import json
import re
from pathlib import Path

from opencomplai_core.scanner.feature_types import ManifestPackage
from opencomplai_core.scanner.inventory import RepoInventory

MANIFEST_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "Pipfile",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
}


def _parse_requirements(
    text: str, location: str, scope, source: str
) -> list[ManifestPackage]:
    packages: list[ManifestPackage] = []
    for i, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        name = re.split(r"[<>=!~\[]", line)[0].strip().lower()
        if name:
            packages.append(
                ManifestPackage(
                    name=name,
                    location=f"{location}:{i}",
                    scope=scope,
                    source=source,
                )
            )
    return packages


def _parse_package_json(
    text: str, location: str, scope, source: str
) -> list[ManifestPackage]:
    packages: list[ManifestPackage] = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return packages
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        deps = data.get(section, {})
        if isinstance(deps, dict):
            for name in deps:
                packages.append(
                    ManifestPackage(
                        name=name.lower(),
                        location=f"{location}:{section}",
                        scope=scope,
                        source=source,
                    )
                )
    return packages


def extract_manifest_features(inventory: RepoInventory) -> list[ManifestPackage]:
    results: list[ManifestPackage] = []
    for entry in inventory.entries:
        name = Path(entry.rel_path).name
        if name not in MANIFEST_FILES and not name.endswith(".lock"):
            if name != "requirements.txt" and "requirements" not in name:
                if name not in ("package.json", "pyproject.toml"):
                    continue

        if entry.is_binary:
            continue

        try:
            text = Path(entry.path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if name == "requirements.txt" or (
            name.startswith("requirements") and not name.endswith(".md")
        ):
            results.extend(
                _parse_requirements(text, entry.rel_path, entry.scope, "requirements")
            )
        elif name == "package.json":
            results.extend(
                _parse_package_json(text, entry.rel_path, entry.scope, "npm")
            )
        elif name == "pyproject.toml":
            for match in re.finditer(r'"([^"]+)"\s*=', text):
                pkg = match.group(1).lower()
                if pkg and not pkg.startswith("tool"):
                    results.append(
                        ManifestPackage(
                            name=pkg,
                            location=f"{entry.rel_path}:dep",
                            scope=entry.scope,
                            source="pyproject",
                        )
                    )
    return results
