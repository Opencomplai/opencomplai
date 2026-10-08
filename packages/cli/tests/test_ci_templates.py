"""SU-113b: the GitLab CI component and the Azure Pipelines template.

Pure file checks (yaml and re only): both templates must parse, run the same
`opencomplai check` flags, publish JUnit even when the check fails, and the
guide must embed the Azure file verbatim and link both templates.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPONENT = _REPO_ROOT / "templates" / "opencomplai.yml"
_AZURE = _REPO_ROOT / "docs" / "ci" / "azure-pipelines.yml"
_GUIDE = _REPO_ROOT / "docs" / "src" / "guides" / "ci-gitlab-azure.md"

_REQUIRED_FLAGS = ("--sign-if-available", "--report-junit", "--summary-md")
_BLOB = "https://github.com/Opencomplai/opencomplai/blob/main/"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _component_docs() -> list:
    return list(yaml.safe_load_all(_text(_COMPONENT)))


def _check_command(text: str) -> str:
    """The `opencomplai check ...` command with backslash continuations joined."""
    m = re.search(r"^[ \t]*opencomplai check(?:[^\n]*\\\n)*[^\n]*", text, re.M)
    assert m, "no `opencomplai check` command found"
    return re.sub(r"\\\n\s*", " ", m.group(0))


def test_gitlab_component_is_spec_plus_job():
    docs = _component_docs()
    assert len(docs) == 2
    inputs = docs[0]["spec"]["inputs"]
    assert isinstance(inputs, dict)
    for name in (
        "stage",
        "image",
        "version",
        "manifest",
        "extra_args",
        "sarif",
        "push",
    ):
        assert name in inputs
        assert "default" in inputs[name]
        assert "description" in inputs[name]
    job = docs[1]["opencomplai-scan"]
    assert job["stage"] == "$[[ inputs.stage ]]"
    assert job["image"] == "$[[ inputs.image ]]"
    assert job["artifacts"]["reports"]["junit"] == "opencomplai-report.xml"


def test_gitlab_component_interpolates_only_declared_inputs():
    declared = set(_component_docs()[0]["spec"]["inputs"])
    used = set(re.findall(r"\$\[\[\s*inputs\.(\w+)\s*\]\]", _text(_COMPONENT)))
    assert used, "the job references no inputs"
    assert used <= declared, f"undeclared inputs: {sorted(used - declared)}"


def test_component_and_azure_share_check_flags():
    for path in (_COMPONENT, _AZURE):
        cmd = _check_command(_text(path))
        for flag in _REQUIRED_FLAGS:
            assert flag in cmd, f"{path.name}: {flag} missing from `{cmd}`"


def test_junit_published_even_when_check_fails():
    artifacts = _component_docs()[1]["opencomplai-scan"]["artifacts"]
    assert artifacts["when"] == "always"
    steps = yaml.safe_load(_text(_AZURE))["steps"]
    publish = [s for s in steps if s.get("task") == "PublishTestResults@2"]
    assert len(publish) == 1
    assert publish[0]["condition"] == "succeededOrFailed()"
    assert publish[0]["inputs"]["testResultsFormat"] == "JUnit"
    assert publish[0]["inputs"]["testResultsFiles"] == "opencomplai-report.xml"
    scripts = [s["script"] for s in steps if "script" in s]
    assert any("set +e" in s for s in scripts), "check step must save the exit code"
    assert "exit $(OC_EXIT)" in scripts[-1]


def test_azure_pipeline_structure():
    data = yaml.safe_load(_text(_AZURE))
    assert data["trigger"] == ["main"]
    assert data["pr"] == ["main"]
    assert data["pool"]["vmImage"] == "ubuntu-latest"
    tasks = [s.get("task") for s in data["steps"]]
    assert "UsePythonVersion@0" in tasks
    assert "PublishTestResults@2" in tasks
    run = next(s for s in data["steps"] if "opencomplai check" in s.get("script", ""))
    assert run["env"]["OPENCOMPLAI_API_KEY"] == "$(OPENCOMPLAI_API_KEY)"


def test_guide_embeds_azure_verbatim_and_links_both():
    guide = _text(_GUIDE)
    blocks = re.findall(r"```yaml\n(.*?)```", guide, re.S)
    assert _text(_AZURE) in blocks
    assert f"{_BLOB}templates/opencomplai.yml" in guide
    assert f"{_BLOB}docs/ci/azure-pipelines.yml" in guide
    assert "ci-gitlab-azure.md" in _text(_GUIDE.parent / "ci-integration.md")
