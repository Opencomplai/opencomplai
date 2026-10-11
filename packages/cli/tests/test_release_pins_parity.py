"""Every shipped CLI version pin equals the CLI package version.

CL-R1 stamps all of these sites in one commit at release time; this test is the gate
that stops one of them from drifting.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[3]
_PKG = "packages/cli/pyproject.toml"
_ACTION = "integrations/github-action/action.yml"
_COMPONENT = "templates/opencomplai.yml"
_AZURE = "docs/ci/azure-pipelines.yml"
_FORMULA = "packaging/homebrew/opencomplai.rb"
_GUIDE = "docs/src/guides/ci-gitlab-azure.md"
_VERSION_RE = r"(\d+\.\d+\.\d+)"


def _text(rel: str) -> str:
    return (_ROOT / rel).read_text(encoding="utf-8")


def _search(pattern: str, rel: str, flags: int = 0) -> str:
    match = re.search(pattern, _text(rel), flags)
    assert match, f"no pin found in {rel}"
    return match.group(1)


def _cli_version() -> str:
    return tomllib.loads(_text(_PKG))["project"]["version"]


def _pins() -> dict[str, str]:
    """Surface path -> pinned version, one entry per place a release stamps."""
    action = yaml.safe_load(_text(_ACTION))
    component = list(yaml.safe_load_all(_text(_COMPONENT)))
    return {
        _ACTION: str(action["inputs"]["version"]["default"]),
        _COMPONENT: str(component[0]["spec"]["inputs"]["version"]["default"]),
        _AZURE: _search(rf"opencomplai=={_VERSION_RE}", _AZURE),
        _FORMULA: _search(rf"opencomplai-{_VERSION_RE}\.tar\.gz", _FORMULA),
        f"{_GUIDE} (version table row)": _search(
            rf"^\| `version` \| `{_VERSION_RE}` \|", _GUIDE, re.M
        ),
        f"{_GUIDE} (opencomplai== line)": _search(
            rf"opencomplai=={_VERSION_RE}", _GUIDE
        ),
    }


def _stale(pins: dict[str, str], version: str) -> list[str]:
    return [surface for surface, value in pins.items() if value != version]


def test_ci_and_packaging_pins_equal_cli_version():
    version = _cli_version()
    stale = _stale(_pins(), version)
    assert not stale, " ".join(
        f"Stamp opencomplai=={version} into {surface} at release time."
        for surface in stale
    )


def test_parity_reports_a_stale_pin():
    pins = _pins()
    version = _cli_version()
    pins[_AZURE] = "0.0.0"
    assert _stale(pins, version) == [_AZURE]
