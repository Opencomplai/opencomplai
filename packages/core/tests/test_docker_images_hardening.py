"""Guard the service Dockerfiles that the release Trivy gate scans (SU-120)."""

import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PYTHON_SERVICES = ["risk-engine", "evidence-vault", "doc-generator", "egress-proxy"]
ALL_SERVICES = [*PYTHON_SERVICES, "gateway-api"]


def _read(service: str) -> str:
    # A missing Dockerfile raises FileNotFoundError: fail, never skip.
    return (ROOT / "infra" / "docker" / f"{service}.Dockerfile").read_text(
        encoding="utf-8"
    )


def _from_refs(text: str) -> list[str]:
    return re.findall(
        r"^FROM\s+(\S+)(?:\s+AS\s+\S+)?\s*$", text, re.MULTILINE | re.IGNORECASE
    )


def _runtime_stage(text: str) -> str:
    return re.split(r"^FROM\s", text, flags=re.MULTILINE | re.IGNORECASE)[-1]


@pytest.mark.parametrize("service", ALL_SERVICES)
def test_from_lines_pinned_by_digest(service):
    refs = _from_refs(_read(service))
    assert len(refs) == 2, refs
    for ref in refs:
        assert re.search(r"@sha256:[0-9a-f]{64}$", ref), ref
    assert len(set(refs)) == 1, refs


@pytest.mark.parametrize("service", PYTHON_SERVICES)
def test_python_images_frozen_no_dev_and_no_build_tools(service):
    text = _read(service)
    assert re.search(
        r"pip install --no-cache-dir \"?uv==\d+\.\d+\.\d+\"?\s*$", text, re.MULTILINE
    )
    assert not re.search(r"pip install --no-cache-dir uv\s*$", text, re.MULTILINE)
    sync = re.search(r"^RUN uv sync .*$", text, re.MULTILINE)
    assert sync
    assert "--frozen" in sync.group(0)
    assert "--no-dev" in sync.group(0)
    uninstall = re.search(r"pip uninstall[^\n]*", _runtime_stage(text))
    assert uninstall
    for pkg in ("pip", "setuptools", "wheel"):
        assert re.search(rf"\b{pkg}\b", uninstall.group(0)), pkg


def test_gateway_runtime_has_no_package_managers():
    text = _read("gateway-api")
    assert re.search(r"pnpm@\d+\.\d+\.\d+\b", text)
    runtime = _runtime_stage(text)
    assert "apk upgrade" in runtime
    assert re.search(r"rm -rf[^&]*node_modules/npm\b", runtime)
    for tool in ("npx", "corepack", "yarn"):
        assert tool in runtime.split("rm -rf", 1)[1].split("&&")[0], tool
    assert re.search(r"apk add [^&]*\bcurl\b", runtime)


def _workflow_trivy_pin() -> str | None:
    # supply-chain.yml is enterprise-only (.github/ is stripped from the public
    # tree), so an absent file means "nothing to compare"; a present file with
    # no pin still fails.
    path = ROOT / ".github" / "workflows" / "supply-chain.yml"
    if not path.exists():
        return None
    pin = re.search(
        r'TRIVY_VERSION:\s*"(\d+\.\d+\.\d+)"', path.read_text(encoding="utf-8")
    )
    assert pin
    return pin.group(1)


def test_trivy_last_run_lists_five_clean_images():
    # A missing record raises FileNotFoundError: fail, never skip.
    text = (ROOT / "infra" / "docker" / "TRIVY-LAST-RUN.md").read_text(encoding="utf-8")
    pin = _workflow_trivy_pin()
    if pin:
        assert f"Trivy version: {pin}" in text
    else:
        assert re.search(r"Trivy version: \d+\.\d+\.\d+", text)
    assert "--exit-code 1 --ignore-unfixed --severity CRITICAL,HIGH" in text
    rows = re.findall(
        r"^\|\s*([\w-]+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*$",
        text,
        re.MULTILINE,
    )
    rows = [r for r in rows if r[0] != "service" and not r[0].startswith("-")]
    assert sorted(r[0] for r in rows) == sorted(ALL_SERVICES), rows
    for service, image_id, base, high, critical in rows:
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", image_id), (service, image_id)
        digests = {ref.rsplit("@", 1)[1] for ref in _from_refs(_read(service))}
        assert digests == {base}, (service, base, digests)
        assert (high, critical) == ("0", "0"), (service, high, critical)


def test_trivy_pin_check_skipped_without_workflow(monkeypatch, tmp_path):
    shutil.copytree(ROOT / "infra" / "docker", tmp_path / "infra" / "docker")
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    assert _workflow_trivy_pin() is None
    test_trivy_last_run_lists_five_clean_images()
