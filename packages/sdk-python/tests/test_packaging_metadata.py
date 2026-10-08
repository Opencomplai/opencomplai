"""Packaging guards: the meta-package ships the executable; metadata is complete."""

import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PACKAGES = ("sdk-python", "cli", "core", "ai")


def _pyproject(pkg: str) -> dict:
    return tomllib.loads(
        (ROOT / "packages" / pkg / "pyproject.toml").read_text(encoding="utf-8")
    )


def test_meta_package_declares_opencomplai_script():
    scripts = _pyproject("sdk-python")["project"].get("scripts", {})
    assert scripts.get("opencomplai") == "opencomplai_cli.main:app"


def test_meta_package_script_target_importable():
    target = _pyproject("sdk-python")["project"]["scripts"]["opencomplai"]
    module, attr = target.split(":")
    assert callable(getattr(importlib.import_module(module), attr))


def test_all_packages_have_classifiers_and_urls():
    for pkg in PACKAGES:
        project = _pyproject(pkg)["project"]
        classifiers = project.get("classifiers", [])
        assert (
            "License :: OSI Approved :: GNU Affero General Public License v3"
            in classifiers
        ), pkg
        assert "Programming Language :: Python :: 3.11" in classifiers, pkg
        for key in ("Homepage", "Documentation", "Source", "Issues"):
            assert key in project.get("urls", {}), (pkg, key)


def test_smoke_script_covers_uv_tool_and_pipx():
    text = (ROOT / "scripts" / "smoke_wheel_install.sh").read_text(encoding="utf-8")
    assert "uv tool install" in text
    assert "pipx install" in text


def test_installation_doc_has_no_stale_sdk_warning():
    text = (ROOT / "docs" / "src" / "getting-started" / "installation.md").read_text(
        encoding="utf-8"
    )
    assert "Do not run" not in text
    assert "0.1.0-dev" not in text
    assert "uv tool install opencomplai" in text
    assert "pipx install opencomplai" in text


def test_smoke_script_resolves_fresh_typer():
    text = (ROOT / "scripts" / "smoke_wheel_install.sh").read_text(encoding="utf-8")
    assert "--refresh" in text
    assert "importlib.metadata" in text
