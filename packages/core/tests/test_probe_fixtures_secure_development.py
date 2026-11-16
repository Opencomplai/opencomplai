"""The `secure_development` probes against three fixture repositories: nothing, unfilled, filled."""

from __future__ import annotations

import json
from pathlib import Path

import opencomplai_core
import pytest
from opencomplai_core.gap_probes import artifact_gap_status, run_artifact_probe
from opencomplai_core.models import GapStatus

ROOT = (
    Path(opencomplai_core.__file__).parent
    / "probes"
    / "scaffolds"
    / "secure_development"
)
FIXTURES = Path(__file__).parent / "fixtures" / "probes" / "secure_development"
INDEX = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
DOC_REFS = tuple(sorted(INDEX))
# Every probe of this family reads configuration files; none has a scaffold.
CONFIG_TARGETS = {
    "sast_config": ".github/workflows/sast.yml",
    "secret_scanning_config": ".pre-commit-config.yaml",
    "code_review_rules": ".github/CODEOWNERS",
    "ci_test_workflow": ".github/workflows/ci.yml",
    "dependency_update_config": ".github/dependabot.yml",
    "iac_definitions": "deploy/Dockerfile",
}
CONFIG_REFS = tuple(CONFIG_TARGETS)
REFS = DOC_REFS + CONFIG_REFS


def _expected(repo: str, ref: str) -> tuple[GapStatus, float | None]:
    if repo == "empty":
        return GapStatus.MISSING, None
    if repo == "scaffolded":
        if ref in CONFIG_REFS:
            return GapStatus.MISSING, None
        return GapStatus.PARTIAL, 0.35
    return GapStatus.PARTIAL, 0.6


@pytest.mark.parametrize("repo", ["empty", "scaffolded", "evidenced"])
@pytest.mark.parametrize("ref", REFS)
def test_fixture_outcome(repo: str, ref: str):
    row = artifact_gap_status(ref, FIXTURES / repo)
    status, confidence = _expected(repo, ref)
    assert row.status == status
    assert row.status != GapStatus.MET
    if confidence is not None:
        assert row.confidence == confidence
    if repo == "scaffolded" and ref in DOC_REFS:
        assert "unfilled" in row.rationale


def test_the_empty_repo_holds_only_a_gitkeep():
    files = [p.name for p in (FIXTURES / "empty").rglob("*") if p.is_file()]
    assert files == [".gitkeep"]


def test_every_scaffold_is_short_and_has_a_placeholder():
    for ref, entry in INDEX.items():
        text = (ROOT / f"{ref}.md").read_text(encoding="utf-8")
        assert len(text.splitlines()) <= 60
        assert "_fill in_" in text
        assert entry["title"]
        assert not Path(entry["target"]).is_absolute()
    assert sorted(p.stem for p in ROOT.glob("*.md")) == list(DOC_REFS)


def test_scaffolded_files_are_byte_equal_to_their_scaffolds():
    for ref in DOC_REFS:
        target = FIXTURES / "scaffolded" / INDEX[ref]["target"]
        assert target.read_bytes() == (ROOT / f"{ref}.md").read_bytes()


@pytest.mark.parametrize("ref", CONFIG_REFS)
def test_every_config_target_is_found_by_its_probe_in_evidenced(ref: str):
    result = run_artifact_probe(ref, FIXTURES / "evidenced")
    assert CONFIG_TARGETS[ref] in result.found_paths


def test_every_scaffold_target_is_found_by_its_probe_in_evidenced():
    for ref in DOC_REFS:
        result = run_artifact_probe(ref, FIXTURES / "evidenced")
        assert INDEX[ref]["target"] in result.found_paths
