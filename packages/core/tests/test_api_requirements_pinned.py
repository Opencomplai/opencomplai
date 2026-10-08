"""OSS API bundles pin their direct dependencies to the root uv.lock versions."""

import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BUNDLES = ("docs-gen", "egress", "evidence", "risk")
HEADER = "# Pins mirror the root uv.lock and are bumped together with it."
UNPINNED_ALLOWLIST = {
    "vercel-blob": "not in uv.lock; Vercel Blob SDK only needed for STORAGE_BACKEND=vercel_blob"
}

_COMMON = {
    "fastapi": "0.109.0",
    "uvicorn": "0.27.0",
    "cryptography": "42.0",
    "pydantic": "2.0",
    "prometheus-client": "0.19.0",
    "opentelemetry-sdk": "1.22.0",
    "opentelemetry-exporter-prometheus": "0.43b0",
    "opentelemetry-instrumentation-fastapi": "0.43b0",
}
OLD_FLOORS = {
    "docs-gen": {**_COMMON, "httpx": "0.26.0"},
    "egress": {**_COMMON, "httpx": "0.26.0"},
    "risk": dict(_COMMON),
    "evidence": {
        **_COMMON,
        "sqlalchemy": "2.0",
        "alembic": "1.13.0",
        "asyncpg": "0.29.0",
        "aiosqlite": "0.20.0",
        "psycopg2-binary": "2.9",
        "vercel-blob": "0.1.0",
    },
}


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _lock_versions() -> dict[str, str]:
    lock = ROOT / "uv.lock"
    assert lock.is_file(), f"{lock} is missing"
    pkgs = tomllib.loads(lock.read_text(encoding="utf-8"))["package"]
    return {_norm(p["name"]): p["version"] for p in pkgs}


def _path(bundle: str) -> Path:
    return ROOT / "api" / bundle / "requirements.txt"


def _parse(path: Path):
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-e")):
            continue
        m = re.fullmatch(r"([A-Za-z0-9._-]+)(\[[^\]]*\])?\s*(==|>=)\s*(\S+)", line)
        assert m, f"{path}: unparseable line {line!r}"
        yield _norm(m[1]), m[2] or "", m[3], m[4]


def _key(version: str) -> tuple[int, ...]:
    # 0.63b0 -> (0, 63, 0): a bN/aN/rcN suffix counts as a trailing numeric segment.
    return tuple(int(n) for n in re.findall(r"\d+", version))


@pytest.mark.parametrize("bundle", BUNDLES)
def test_api_bundles_pinned_to_uv_lock(bundle):
    path = _path(bundle)
    assert path.is_file(), f"{path} is missing"
    assert "-e ../../packages/core" in path.read_text(encoding="utf-8").splitlines(), (
        f"{path}: -e core line missing"
    )
    lock = _lock_versions()
    for name, _extras, op, version in _parse(path):
        if name in UNPINNED_ALLOWLIST:
            assert op == ">=", f"{path}: {name} must keep its >= floor"
            continue
        assert op == "==", f"{path}: {name} is not pinned with == ({op}{version})"
        assert version == lock[name], (
            f"{path}: {name}=={version} but uv.lock has {lock[name]}"
        )


@pytest.mark.parametrize("bundle", BUNDLES)
def test_pins_satisfy_old_floors(bundle):
    path = _path(bundle)
    seen = set()
    for name, _extras, _op, version in _parse(path):
        seen.add(name)
        floor = OLD_FLOORS[bundle][name]
        assert _key(version) >= _key(floor), (
            f"{path}: {name} {version} is below the old floor {floor}"
        )
    assert seen == set(OLD_FLOORS[bundle]), f"{path}: packages differ from old set"


@pytest.mark.parametrize("bundle", BUNDLES)
def test_header_line_present(bundle):
    path = _path(bundle)
    assert HEADER in path.read_text(encoding="utf-8").splitlines(), (
        f"{path}: header comment missing"
    )
