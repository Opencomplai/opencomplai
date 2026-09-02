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
    "Pipfile.lock",
    "poetry.lock",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
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


# ---------------------------------------------------------------------------
# Non-Python / non-npm ecosystems (SCAN-COVERAGE, finding 82)
#
# `MANIFEST_FILES` has always listed these and `AiDependencyDetector` has always
# claimed java/go/rust support, but `extract_manifest_features` only branched on
# requirements / package.json / pyproject — every other manifest fell through to
# **zero packages**. A Go or Rust service using an AI SDK produced no dependency
# evidence at all, so the scan reported clean for the same reason a genuinely
# AI-free repo does. These parsers close that false-negative gap.
#
# All of them are deliberately shallow: the goal is "which package names appear
# here", not a faithful build-graph resolution. A wrong extra name costs a
# little noise; a missed one costs the evidence the whole scan exists to find.
# ---------------------------------------------------------------------------


def _parse_go_mod(
    text: str, location: str, scope, source: str
) -> list[ManifestPackage]:
    """
    Module paths from `require` directives, both block and single-line forms.

    The module path is kept whole (`github.com/sashabaranov/go-openai`) rather
    than reduced to its last segment: the host and org are what identify the
    vendor, and `go-openai` alone would collide across ecosystems.
    """
    packages: list[ManifestPackage] = []
    in_block = False
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("//")[0].strip()
        if not line:
            continue
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue

        candidate = line
        if line.startswith("require "):
            candidate = line[len("require ") :].strip()
        elif not in_block:
            continue

        parts = candidate.split()
        if not parts:
            continue
        name = parts[0].strip().lower()
        # `require ( ... )` blocks can carry `// indirect` markers, already
        # stripped above. Skip anything that is plainly not a module path.
        # A module path is host-qualified: it contains a "/" (most modules) or
        # at least a dot (a bare domain like "gopkg.in"). Without the explicit
        # grouping the `or` binds loosely enough to admit "(" and directive
        # keywords such as "go" and "toolchain".
        if name and not name.startswith("(") and ("/" in name or "." in name):
            packages.append(
                ManifestPackage(
                    name=name, location=f"{location}:{i}", scope=scope, source=source
                )
            )
    return packages


def _parse_go_sum(
    text: str, location: str, scope, source: str
) -> list[ManifestPackage]:
    """Module paths from go.sum. Each module appears twice; emit it once."""
    packages: list[ManifestPackage] = []
    seen: set[str] = set()
    for i, raw in enumerate(text.splitlines(), start=1):
        parts = raw.split()
        if not parts:
            continue
        name = parts[0].strip().lower()
        if name and name not in seen:
            seen.add(name)
            packages.append(
                ManifestPackage(
                    name=name, location=f"{location}:{i}", scope=scope, source=source
                )
            )
    return packages


_CARGO_SECTION = re.compile(r"^\[([^\]]+)\]\s*$")
_TOML_KEY = re.compile(r"^([A-Za-z0-9_.-]+)\s*=")


def _parse_cargo_toml(
    text: str, location: str, scope, source: str
) -> list[ManifestPackage]:
    """
    Crate names from any `[dependencies]`-family table.

    Only dependency tables are read — `[package]` would otherwise contribute
    keys like `name` and `edition` as if they were crates.
    """
    packages: list[ManifestPackage] = []
    section = ""
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        header = _CARGO_SECTION.match(line)
        if header:
            section = header.group(1).strip()
            # `[dependencies.foo]` declares the crate `foo` in its own table.
            if section.startswith(
                ("dependencies.", "dev-dependencies.", "build-dependencies.")
            ):
                name = section.split(".", 1)[1].strip().lower()
                if name:
                    packages.append(
                        ManifestPackage(
                            name=name,
                            location=f"{location}:{i}",
                            scope=scope,
                            source=source,
                        )
                    )
            continue
        if section not in ("dependencies", "dev-dependencies", "build-dependencies"):
            continue
        key = _TOML_KEY.match(line)
        if key:
            packages.append(
                ManifestPackage(
                    name=key.group(1).strip().lower(),
                    location=f"{location}:{i}",
                    scope=scope,
                    source=source,
                )
            )
    return packages


def _parse_cargo_lock(
    text: str, location: str, scope, source: str
) -> list[ManifestPackage]:
    """Crate names from `[[package]]` blocks in Cargo.lock."""
    packages: list[ManifestPackage] = []
    in_package = False
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line == "[[package]]":
            in_package = True
            continue
        if line.startswith("["):
            in_package = False
            continue
        if in_package and line.startswith("name"):
            match = re.match(r'name\s*=\s*"([^"]+)"', line)
            if match:
                packages.append(
                    ManifestPackage(
                        name=match.group(1).lower(),
                        location=f"{location}:{i}",
                        scope=scope,
                        source=source,
                    )
                )
    return packages


_POM_DEP = re.compile(r"<dependency>(.*?)</dependency>", re.DOTALL | re.IGNORECASE)
_POM_GROUP = re.compile(r"<groupId>\s*([^<]+?)\s*</groupId>", re.IGNORECASE)
_POM_ARTIFACT = re.compile(r"<artifactId>\s*([^<]+?)\s*</artifactId>", re.IGNORECASE)


def _parse_pom_xml(
    text: str, location: str, scope, source: str
) -> list[ManifestPackage]:
    """
    `groupId:artifactId` pairs from Maven `<dependency>` elements.

    Parsed with a regex rather than an XML parser on purpose: this runs over
    attacker-supplied repository content, and Python's stdlib XML parsers are
    vulnerable to entity-expansion attacks on untrusted input. A regex cannot
    be induced to allocate a gigabyte.
    """
    packages: list[ManifestPackage] = []
    for match in _POM_DEP.finditer(text):
        block = match.group(1)
        group = _POM_GROUP.search(block)
        artifact = _POM_ARTIFACT.search(block)
        if not artifact:
            continue
        line = text[: match.start()].count("\n") + 1
        name = (
            f"{group.group(1)}:{artifact.group(1)}" if group else artifact.group(1)
        ).lower()
        packages.append(
            ManifestPackage(
                name=name, location=f"{location}:{line}", scope=scope, source=source
            )
        )
    return packages


_GRADLE_DEP = re.compile(
    r"""(?:implementation|api|compileOnly|runtimeOnly|testImplementation
        |testCompileOnly|annotationProcessor|kapt|ksp)
        \s*[\s(]\s*["']([^"']+)["']""",
    re.VERBOSE,
)


def _parse_gradle(
    text: str, location: str, scope, source: str
) -> list[ManifestPackage]:
    """
    Coordinates from Gradle dependency declarations, Groovy and Kotlin DSL.

    Only `group:artifact` is kept; the version is dropped so the same
    dependency at two versions does not read as two different packages.
    """
    packages: list[ManifestPackage] = []
    for match in _GRADLE_DEP.finditer(text):
        coordinate = match.group(1).strip()
        parts = coordinate.split(":")
        name = ":".join(parts[:2]).lower() if len(parts) >= 2 else coordinate.lower()
        if name:
            line = text[: match.start()].count("\n") + 1
            packages.append(
                ManifestPackage(
                    name=name, location=f"{location}:{line}", scope=scope, source=source
                )
            )
    return packages


def _parse_pipfile(
    text: str, location: str, scope, source: str
) -> list[ManifestPackage]:
    """Package names from Pipfile's `[packages]` / `[dev-packages]` tables."""
    packages: list[ManifestPackage] = []
    section = ""
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        header = _CARGO_SECTION.match(line)
        if header:
            section = header.group(1).strip()
            continue
        if section not in ("packages", "dev-packages"):
            continue
        key = _TOML_KEY.match(line)
        if key:
            packages.append(
                ManifestPackage(
                    name=key.group(1).strip().strip('"').lower(),
                    location=f"{location}:{i}",
                    scope=scope,
                    source=source,
                )
            )
    return packages


def _parse_json_lock(
    text: str, location: str, scope, source: str
) -> list[ManifestPackage]:
    """
    Package names from an npm/Pipfile JSON lockfile.

    npm v2+ lockfiles key `packages` by path (`node_modules/openai`); the last
    path segment is the package name. v1 lockfiles use a flat `dependencies`
    map keyed by name directly. Both shapes are handled because both are still
    in the wild.
    """
    packages: list[ManifestPackage] = []
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return packages
    if not isinstance(data, dict):
        return packages

    names: set[str] = set()
    entries = data.get("packages")
    if isinstance(entries, dict):
        for key in entries:
            if not key:
                continue  # the root project itself
            names.add(key.rsplit("node_modules/", 1)[-1])
    for section in ("dependencies", "develop", "default"):
        entries = data.get(section)
        if isinstance(entries, dict):
            names.update(entries.keys())

    for name in sorted(n.strip().lower() for n in names if n and n.strip()):
        packages.append(
            ManifestPackage(
                name=name, location=f"{location}:lock", scope=scope, source=source
            )
        )
    return packages


def _parse_poetry_lock(
    text: str, location: str, scope, source: str
) -> list[ManifestPackage]:
    """Package names from `[[package]]` blocks in poetry.lock (same shape as Cargo.lock)."""
    return _parse_cargo_lock(text, location, scope, source)


#: filename -> (parser, source label). Explicit dispatch: the previous nested
#: `if`/`continue` chain silently dropped anything it did not name, which is
#: how five ecosystems ended up listed but unparsed.
_PARSERS = {
    "package.json": (_parse_package_json, "npm"),
    "package-lock.json": (_parse_json_lock, "npm-lock"),
    "Pipfile": (_parse_pipfile, "pipfile"),
    "Pipfile.lock": (_parse_json_lock, "pipfile-lock"),
    "poetry.lock": (_parse_poetry_lock, "poetry-lock"),
    "go.mod": (_parse_go_mod, "go"),
    "go.sum": (_parse_go_sum, "go-sum"),
    "Cargo.toml": (_parse_cargo_toml, "cargo"),
    "Cargo.lock": (_parse_cargo_lock, "cargo-lock"),
    "pom.xml": (_parse_pom_xml, "maven"),
    "build.gradle": (_parse_gradle, "gradle"),
    "build.gradle.kts": (_parse_gradle, "gradle"),
}


def extract_manifest_features(inventory: RepoInventory) -> list[ManifestPackage]:
    results: list[ManifestPackage] = []
    for entry in inventory.entries:
        name = Path(entry.rel_path).name
        if entry.is_binary:
            continue

        parser = _PARSERS.get(name)
        is_requirements = name.startswith("requirements") and not name.endswith(".md")
        if parser is None and not is_requirements and name != "pyproject.toml":
            continue

        try:
            text = Path(entry.path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if parser is not None:
            fn, source = parser
            results.extend(fn(text, entry.rel_path, entry.scope, source))
        elif is_requirements:
            results.extend(
                _parse_requirements(text, entry.rel_path, entry.scope, "requirements")
            )
        else:  # pyproject.toml
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
