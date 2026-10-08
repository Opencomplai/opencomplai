"""Security and supply-chain docs must not claim what the workflows do not do.

Monorepo-only: `.github/` is not published to the public repo, so the module
skips when the workflows are absent. Reads files only; never runs a workflow.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github" / "workflows"
PUBLISH = WORKFLOWS / "publish-pypi.yml"

if not PUBLISH.is_file():
    pytest.skip(
        "monorepo-only test (public tree has no .github/workflows)",
        allow_module_level=True,
    )

GUARD_STEP = "Check tag matches package versions"
PACKAGES = ("core", "cli", "ai", "sdk-python")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _publish() -> dict:
    return yaml.safe_load(_text(PUBLISH))


def _steps(job: str) -> list[dict]:
    return _publish()["jobs"][job]["steps"]


def _flat_steps() -> list[dict]:
    """Steps of the build job then the publish job, in file order."""
    jobs = _publish()["jobs"]
    return jobs["build"]["steps"] + jobs["publish"]["steps"]


def test_security_md_claims_match_workflows() -> None:
    sec = _text(ROOT / "SECURITY.md")
    publish = _text(PUBLISH)
    all_workflows = "\n".join(_text(p) for p in WORKFLOWS.glob("*.yml"))
    # (claim regex in SECURITY.md, required substring, workflow file)
    table = [
        (r"npm audit", "npm audit", None),
        (r"SBOM", "cyclonedx", PUBLISH),
        (r"cosign", "cosign sign", WORKFLOWS / "supply-chain.yml"),
        (r"pip-audit", "pip-audit", WORKFLOWS / "ci-python.yml"),
        (r"attest", "attestations: true", PUBLISH),
    ]
    for claim, needle, wf in table:
        if re.search(claim, sec, re.I):
            haystack = all_workflows if wf is None else _text(wf)
            assert needle.lower() in haystack.lower(), (
                f"SECURITY.md claims {claim!r} but {wf or 'no workflow'} lacks {needle!r}"
            )
    assert "cyclonedx" in publish.lower()
    # Release files are not Ed25519-signed; the only mention may be signing.py
    # for compliance artifacts.
    for line in sec.splitlines():
        if re.search(r"ed25519", line, re.I) and re.search(r"release", line, re.I):
            if not re.search(r"\bnot\b", line, re.I):
                pytest.fail(f"SECURITY.md claims Ed25519 release signing: {line!r}")


def test_supply_chain_page_claims_match_workflows() -> None:
    page = _text(ROOT / "docs" / "src" / "security" / "supply-chain.md")
    attests = any(
        "attest-build-provenance" in _text(p) for p in WORKFLOWS.glob("*.yml")
    )
    if not attests:
        # Allowed only as an explicit "not attested" statement.
        for line in page.splitlines():
            if re.search(r"SLSA|attest-build-provenance|gh attestation", line):
                assert re.search(r"\bnot\b", line, re.I), (
                    f"supply-chain page claims provenance no workflow produces: {line!r}"
                )
    assert ":1.0.0" not in page


def test_workflow_referenced_docs_exist() -> None:
    pat = re.compile(r"(?:\.\./)*(docs/[\w./-]+\.md)")
    missing = []
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        for rel in pat.findall(_text(wf)):
            if not (ROOT / rel).is_file():
                missing.append(f"{wf.name}: {rel}")
    assert not missing, f"workflows reference missing docs: {missing}"


def test_publish_workflow_has_version_guard() -> None:
    step = next((s for s in _steps("build") if s.get("name") == GUARD_STEP), None)
    assert step is not None, f"no build step named {GUARD_STEP!r}"
    assert "github.ref_type == 'tag'" in step["if"]
    assert step["env"]["GITHUB_REF_NAME"] == "${{ github.ref_name }}"
    assert "${{" not in step["run"], "tag must reach the script via env only"
    names = [s.get("name") for s in _steps("build")]
    assert names.index(GUARD_STEP) < names.index("Build all distributions")


def _run_guard(tmp: Path, tag: str, versions: dict[str, str]) -> int:
    step = next(s for s in _steps("build") if s.get("name") == GUARD_STEP)
    assert step["shell"] == "python"
    for pkg in PACKAGES:
        d = tmp / "packages" / pkg
        d.mkdir(parents=True)
        (d / "pyproject.toml").write_text(
            f'[project]\nname = "x"\nversion = "{versions[pkg]}"\n', encoding="utf-8"
        )
    env = {**os.environ, "GITHUB_REF_NAME": tag}
    return subprocess.run(
        [sys.executable, "-c", step["run"]], cwd=tmp, env=env, capture_output=True
    ).returncode


def test_version_guard_script_rejects_mismatch(tmp_path: Path) -> None:
    real = {
        p: tomllib.loads(_text(ROOT / "packages" / p / "pyproject.toml"))["project"][
            "version"
        ]
        for p in PACKAGES
    }
    version = real["core"]
    assert len(set(real.values())) == 1, f"package versions differ: {real}"
    ok = tmp_path / "ok"
    ok.mkdir()
    assert _run_guard(ok, f"v{version}", real) == 0
    wrong_tag = tmp_path / "wrong_tag"
    wrong_tag.mkdir()
    assert _run_guard(wrong_tag, "v999.0.0", real) != 0
    skewed = tmp_path / "skewed"
    skewed.mkdir()
    assert _run_guard(skewed, f"v{version}", {**real, "ai": "0.0.1"}) != 0


def test_publish_workflow_order() -> None:
    names = [s.get("name", "") for s in _flat_steps()]
    uses = [str(s.get("uses", "")) for s in _flat_steps()]
    smoke = names.index("Wheel smoke test")
    first_publish = next(i for i, u in enumerate(uses) if "gh-action-pypi-publish" in u)
    assert smoke < first_publish
    assert "scripts/smoke_wheel_install.sh" in _flat_steps()[smoke]["run"]
    assert names.index("Build all distributions") < smoke


def test_publish_workflow_defines_cyclonedx_sbom() -> None:
    wf = _publish()
    triggers = wf.get("on") or wf.get(True)
    assert "workflow_dispatch" in triggers
    assert "push" in triggers
    jobs = wf["jobs"]
    build = jobs["build"]
    assert "environment" not in build
    assert "if" not in build
    sbom = next(
        s for s in build["steps"] if s.get("name") == "Generate CycloneDX SBOMs"
    )
    assert "if" not in sbom
    assert "cyclonedx" in sbom["run"].lower()
    upload = [
        s
        for s in build["steps"]
        if "upload-artifact" in str(s.get("uses", ""))
        and "sbom" in str(s.get("with", {}).get("path", ""))
    ]
    assert upload, "SBOMs are not uploaded as an artifact"
    publish = jobs["publish"]
    assert publish["needs"] == "build"
    assert "github.event_name == 'push'" in publish["if"]
