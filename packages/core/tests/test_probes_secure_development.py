"""The secure_development probe family: each ref finds a real file, not a bare one."""

from __future__ import annotations

from pathlib import Path

import pytest
from opencomplai_core.gap_probes import artifact_gap_status, probe_exists
from opencomplai_core.models import GapStatus
from opencomplai_core.probe_registry import parse_probe_file

PROBE_FILE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "opencomplai_core"
    / "probes"
    / "secure_development.json"
)

# ref -> (path, file text with a marker, file text of the same name without one)
CASES: dict[str, tuple[str, str, str]] = {
    "sast_config": (
        ".github/workflows/sast.yml",
        "jobs:\n  scan:\n    steps:\n      - uses: github/codeql-action/analyze@v3\n",
        "name: release\njobs:\n  publish:\n    steps:\n      - run: echo done\n",
    ),
    "secret_scanning_config": (
        ".pre-commit-config.yaml",
        "repos:\n  - repo: https://github.com/gitleaks/gitleaks\n    hooks:\n      - id: gitleaks\n",
        "repos:\n  - repo: local\n    hooks:\n      - id: format\n",
    ),
    "code_review_rules": (
        ".github/CODEOWNERS",
        "# owners\n* @acme/platform-team\n",
        "# owners to be decided\n",
    ),
    "ci_test_workflow": (
        ".github/workflows/ci.yml",
        "jobs:\n  test:\n    steps:\n      - run: uv run pytest -q\n",
        "jobs:\n  build:\n    steps:\n      - run: echo build\n",
    ),
    "dependency_update_config": (
        ".github/dependabot.yml",
        "version: 2\nupdates:\n  - package-ecosystem: pip\n    directory: /\n    schedule:\n      interval: weekly\n",
        "# nothing configured yet\n",
    ),
    "iac_definitions": (
        "deploy/Dockerfile",
        "FROM python:3.12-slim\nCOPY . /app\n",
        "# placeholder\nCOPY . /app\n",
    ),
}


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_file_parses_with_the_six_refs():
    probes = parse_probe_file(PROBE_FILE)
    assert set(probes) == set(CASES)


@pytest.mark.parametrize("ref", sorted(CASES))
def test_ref_is_registered(ref: str):
    assert probe_exists(ref)


@pytest.mark.parametrize("ref", sorted(CASES))
def test_empty_repo_is_missing(tmp_path: Path, ref: str):
    assert artifact_gap_status(ref, tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize("ref", sorted(CASES))
def test_matching_file_without_the_marker_is_missing(tmp_path: Path, ref: str):
    rel, _good, bare = CASES[ref]
    _write(tmp_path, rel, bare)
    assert artifact_gap_status(ref, tmp_path).status == GapStatus.MISSING


@pytest.mark.parametrize("ref", sorted(CASES))
def test_realistic_file_is_partial_06(tmp_path: Path, ref: str):
    rel, good, _bare = CASES[ref]
    _write(tmp_path, rel, good)
    row = artifact_gap_status(ref, tmp_path)
    assert row.status == GapStatus.PARTIAL
    assert row.confidence == pytest.approx(0.6)
