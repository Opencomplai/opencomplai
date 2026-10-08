"""Offline structural checks for the Homebrew formula and its docs."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_FORMULA = _ROOT / "packaging" / "homebrew" / "opencomplai.rb"
_README = _ROOT / "packaging" / "homebrew" / "README.md"
_INSTALL_DOC = _ROOT / "docs" / "src" / "getting-started" / "installation.md"
_SDK = _ROOT / "packages" / "sdk-python" / "pyproject.toml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _vtuple(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in text.split("."))


def test_formula_structure_lint() -> None:
    text = _read(_FORMULA)
    assert text.splitlines()[0] == "# frozen_string_literal: true"
    for needle in (
        "class Opencomplai < Formula",
        "include Language::Python::Virtualenv",
        "homepage",
        'url "https://',
        'license "AGPL-3.0-only"',
        'depends_on "python@3',
        "virtualenv_install_with_resources",
    ):
        assert needle in text, needle
    assert re.search(r'^\s*sha256 "[0-9a-f]{64}"$', text, re.M)
    assert "\t" not in text
    for line in text.split("\n"):
        assert line == line.rstrip(), repr(line)
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    desc = re.search(r'^\s*desc "([^"]*)"$', text, re.M)
    assert desc, "desc missing"
    d = desc.group(1)
    assert len(d) < 80
    assert not d.endswith(".")
    assert not d.startswith(("A ", "An ", "The ", "Opencomplai"))


def test_formula_test_block_runs_version() -> None:
    text = _read(_FORMULA)
    assert "test do" in text
    block = text.split("test do", 1)[1]
    assert "opencomplai --version" in block
    assert "assert_match" in block


def test_formula_matches_package_metadata() -> None:
    project = tomllib.loads(_read(_SDK))["project"]
    text = _read(_FORMULA)
    url = re.search(r'^\s*url "([^"]+)"$', text, re.M)
    assert url
    assert f"/{project['name']}/" in url.group(1)
    m = re.search(r"opencomplai-(\d+\.\d+\.\d+)\.tar\.gz$", url.group(1))
    assert m, url.group(1)
    # the formula targets the next release, so it may be ahead of the tree
    assert _vtuple(m.group(1)) >= _vtuple(project["version"])
    lic = re.search(r'^\s*license "([^"]+)"$', text, re.M)
    assert lic
    assert lic.group(1) == project["license"]["text"]
    py = re.search(r'depends_on "python@3\.(\d+)"', text)
    assert py
    assert int(py.group(1)) >= 11
    assert project["requires-python"] == ">=3.11"


def test_installation_doc_describes_homebrew_tap() -> None:
    doc = _read(_INSTALL_DOC)
    assert "brew install Opencomplai/tap/opencomplai" in doc
    assert "tap" in doc
    assert any(s in doc for s in ("not yet published", "planned", "once the tap"))


def test_tap_readme_lists_release_steps() -> None:
    readme = _read(_README)
    for needle in (
        "brew style",
        "brew audit",
        "update-python-resources",
        "Formula/opencomplai.rb",
        "homebrew-tap",
    ):
        assert needle in readme, needle
