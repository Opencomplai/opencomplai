"""
Every package's ``__version__`` must equal the version in its own
``pyproject.toml``.

They drifted: all four packages declared ``__version__ = "0.1.0"`` while their
``pyproject.toml`` said ``0.2.0``. That is not cosmetic — ``__version__`` is
what ``opencomplai --version`` prints and what is stamped into scan artifacts
and reports as ``tool_version``, so every artifact produced named a version that
was never released. For a tool whose output is meant to be audit evidence,
"which version produced this" has to be true.

The check reads both files as text rather than importing the packages, so it
does not depend on ``PYTHONPATH`` and cannot be fooled by a stale copy of the
package installed in ``site-packages`` — which is exactly the situation this
repository is in.
"""

from __future__ import annotations

import json
import re
import shutil
import tomllib
from pathlib import Path

import pytest

_PACKAGES_DIR = Path(__file__).resolve().parents[2]
_ROOT = Path(__file__).resolve().parents[3]

# (distribution directory, import package name)
_PACKAGES = [
    ("core", "opencomplai_core"),
    ("cli", "opencomplai_cli"),
    ("ai", "opencomplai_ai"),
    ("sdk-python", "opencomplai"),
]


def _pyproject_version(pyproject: Path) -> str:
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        match = re.match(r'^version\s*=\s*"([^"]+)"', line.strip())
        if match:
            return match.group(1)
    raise AssertionError(f"no version declared in {pyproject}")


def _dunder_version(init_py: Path) -> str:
    for line in init_py.read_text(encoding="utf-8").splitlines():
        match = re.match(r'^__version__\s*=\s*"([^"]+)"', line.strip())
        if match:
            return match.group(1)
    raise AssertionError(f"no __version__ declared in {init_py}")


@pytest.mark.parametrize(("dist_dir", "module"), _PACKAGES)
def test_dunder_version_matches_pyproject(dist_dir: str, module: str) -> None:
    pyproject = _PACKAGES_DIR / dist_dir / "pyproject.toml"
    init_py = _PACKAGES_DIR / dist_dir / "src" / module / "__init__.py"

    assert pyproject.is_file(), pyproject
    assert init_py.is_file(), init_py

    declared = _pyproject_version(pyproject)
    exported = _dunder_version(init_py)

    assert exported == declared, (
        f"{module}.__version__ is {exported!r} but {dist_dir}/pyproject.toml "
        f"declares {declared!r}. Every artifact this package stamps would carry "
        f"the wrong version."
    )


# --- services and gateway -------------------------------------------------
# The services and the gateway report a version of their own (FastAPI/Fastify
# ``version=``, the gateway ``/health`` and ``/v1/status`` bodies, openapi.yaml).
# They sat at ``0.1.0-dev`` while the packages were released. Everything below
# reads text only, relative to the repository root.

_SERVICES = [
    ("risk-engine", "opencomplai_risk_engine"),
    ("evidence-vault", "opencomplai_evidence_vault"),
    ("doc-generator", "opencomplai_doc_generator"),
    ("egress-proxy", "opencomplai_egress_proxy"),
]
_GATEWAY = "services/gateway-api"
_GATEWAY_TS = [f"{_GATEWAY}/src/routes/health.ts", f"{_GATEWAY}/src/routes/status.ts"]
_GATEWAY_OPENAPI = f"{_GATEWAY}/openapi.yaml"
_PYPROJECTS = [f"packages/{d}/pyproject.toml" for d, _ in _PACKAGES] + [
    f"services/{d}/pyproject.toml" for d, _ in _SERVICES
]
_PACKAGE_JSON = f"{_GATEWAY}/package.json"
# The first `version="x"` after `FastAPI(`; skips unrelated literals further down,
# such as risk-engine's ModelMetadata version. ponytail: regex, not an AST walk;
# a version kwarg placed after a later literal would still be found first.
_APP_VERSION = r'(?s)FastAPI\(.*?\bversion="([^"]+)"'
_SERVICE_MAINS = {d: f"services/{d}/src/{m}/main.py" for d, m in _SERVICES}


def _manifest_versions(root: Path) -> dict[str, str]:
    versions = {p: _pyproject_version(root / p) for p in _PYPROJECTS}
    versions[_PACKAGE_JSON] = json.loads((root / _PACKAGE_JSON).read_text("utf-8"))[
        "version"
    ]
    return versions


def _literals(path: Path, pattern: str) -> list[str]:
    return re.findall(pattern, path.read_text(encoding="utf-8"), flags=re.M)


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _floor_mismatches(root: Path, core: str, cli: str) -> list[str]:
    current = {"opencomplai-core": core, "opencomplai-cli": cli}
    out: list[str] = []
    for rel in _PYPROJECTS:
        project = tomllib.loads((root / rel).read_text("utf-8"))["project"]
        reqs = list(project.get("dependencies", []))
        for extra in project.get("optional-dependencies", {}).values():
            reqs += extra
        for req in reqs:
            m = re.match(r"\s*([A-Za-z0-9_.-]+)\s*(?:\[[^\]]*\])?\s*(.*)", req)
            if not m or _norm(m.group(1)) not in current:
                continue
            floor = re.search(r">=\s*([^,;\s]+)", m.group(2))
            want = current[_norm(m.group(1))]
            if not floor or floor.group(1) != want:
                out.append(f"{rel}: {req!r} must be >={want}")
    return out


def _mismatches(root: Path) -> list[str]:
    """One line per disagreement; empty when every manifest and literal agrees."""
    versions = _manifest_versions(root)
    core = versions["packages/core/pyproject.toml"]
    out = [f"{p} is {v!r}, core is {core!r}" for p, v in versions.items() if v != core]
    for d, _ in _SERVICES:
        main = _SERVICE_MAINS[d]
        found = _literals(root / main, _APP_VERSION)
        own = versions[f"services/{d}/pyproject.toml"]
        if found != [own]:
            out.append(f"{main} reports {found!r}, its pyproject says {own!r}")
    gw = versions[_PACKAGE_JSON]
    for rel in _GATEWAY_TS:
        found = _literals(root / rel, r"\bversion: '([^']+)'")
        if found != [gw]:
            out.append(f"{rel} reports {found!r}, package.json says {gw!r}")
    found = _literals(root / _GATEWAY_OPENAPI, r"^  version: (\S+)")
    if found != [gw]:
        out.append(
            f"{_GATEWAY_OPENAPI} info.version is {found!r}, package.json says {gw!r}"
        )
    cli = versions["packages/cli/pyproject.toml"]
    out += _floor_mismatches(root, core, cli)
    return out


def test_nine_manifests_are_discovered() -> None:
    versions = _manifest_versions(_ROOT)
    assert len(versions) == 9
    assert all((_ROOT / p).is_file() for p in versions)


def test_all_manifests_share_core_version() -> None:
    core = _pyproject_version(_ROOT / "packages/core/pyproject.toml")
    bad = [
        f"{p} is {v!r}, core is {core!r}"
        for p, v in _manifest_versions(_ROOT).items()
        if v != core
    ]
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize(("service", "module"), _SERVICES)
def test_service_reported_version_matches_manifest(service: str, module: str) -> None:
    own = _pyproject_version(_ROOT / f"services/{service}/pyproject.toml")
    found = _literals(_ROOT / _SERVICE_MAINS[service], _APP_VERSION)
    assert found == [own], (
        f"{_SERVICE_MAINS[service]} reports {found!r}, pyproject says {own!r}"
    )


def test_gateway_reported_versions_match_package_json() -> None:
    bad = [m for m in _mismatches(_ROOT) if m.startswith(_GATEWAY)]
    assert not bad, "\n".join(bad)


def test_internal_floors_equal_current_version() -> None:
    core = _pyproject_version(_ROOT / "packages/core/pyproject.toml")
    cli = _pyproject_version(_ROOT / "packages/cli/pyproject.toml")
    bad = _floor_mismatches(_ROOT, core, cli)
    assert not bad, "\n".join(bad)


def test_detects_disagreement(tmp_path: Path) -> None:
    files = [
        *_PYPROJECTS,
        _PACKAGE_JSON,
        *_GATEWAY_TS,
        _GATEWAY_OPENAPI,
        *_SERVICE_MAINS.values(),
    ]
    for rel in files:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_ROOT / rel, tmp_path / rel)
    assert _mismatches(tmp_path) == []

    target = tmp_path / "services/risk-engine/pyproject.toml"
    target.write_text(
        target.read_text("utf-8").replace('version = "', 'version = "9.9.9" #', 1),
        encoding="utf-8",
    )
    result = _mismatches(tmp_path)
    assert result
    assert any("services/risk-engine/pyproject.toml" in m for m in result)
