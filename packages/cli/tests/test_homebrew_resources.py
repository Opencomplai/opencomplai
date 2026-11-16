"""Behaviour guards for packaging/homebrew/resources.py (file URLs only, no network)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "packaging" / "homebrew" / "resources.py"
_FORMULA = _ROOT / "packaging" / "homebrew" / "opencomplai.rb"
_NOW = "2026-11-08T12:00:00+00:00"
_OLD = "2026-10-01T09:00:00.000000Z"
_YOUNG = "2026-11-08T11:00:00.000000Z"


def _pypi(
    base: Path, name: str, version: str, *, uploaded: str, sdist: bool = True
) -> None:
    urls = [
        {"packagetype": "bdist_wheel", "filename": f"{name}-{version}-py3-none-any.whl"}
    ]
    if sdist:
        urls.append(
            {
                "packagetype": "sdist",
                "filename": f"{name}-{version}.tar.gz",
                "url": f"https://files.pythonhosted.org/packages/aa/bb/cc/{name}-{version}.tar.gz",
                "digests": {"sha256": (name[0] * 64)},
                "upload_time_iso_8601": uploaded,
            }
        )
    path = base / name / version / "json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"urls": urls}), encoding="utf-8")


def _run(
    tmp_path: Path, report_names: list[tuple[str, str]], *, formula: Path | None = None
):
    formula = formula or tmp_path / "opencomplai.rb"
    if not formula.exists():
        formula.write_bytes(_FORMULA.read_bytes())
    before = formula.read_bytes()
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "install": [
                    {"metadata": {"name": n, "version": v}} for n, v in report_names
                ]
            }
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "HOMEBREW_PYPI_BASE": tmp_path.as_uri()}
    proc = subprocess.run(
        [sys.executable, "-I", str(_SCRIPT), str(report), str(formula), "--now", _NOW],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc, formula, before


def test_writes_sorted_blocks_and_exempts_our_own_young_packages(
    tmp_path: Path,
) -> None:
    _pypi(tmp_path, "zeta-pkg", "1.0", uploaded=_OLD)
    _pypi(tmp_path, "alpha-pkg", "2.0", uploaded=_OLD)
    _pypi(tmp_path, "opencomplai-core", "0.1.0", uploaded=_YOUNG)
    names = [
        ("Zeta_Pkg", "1.0"),
        ("opencomplai", "0.1.0"),
        ("opencomplai-core", "0.1.0"),
        ("alpha-pkg", "2.0"),
    ]
    proc, formula, _ = _run(tmp_path, names)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    text = formula.read_text(encoding="utf-8")
    order = [
        ln.split('"')[1] for ln in text.splitlines() if ln.startswith('  resource "')
    ]
    assert order == ["alpha-pkg", "opencomplai-core", "zeta-pkg"]
    assert 'sha256 "' + "a" * 64 + '"' in text
    assert "# RESOURCES:" not in text
    assert text.endswith("\n")
    assert not text.endswith("\n\n")
    assert "  def install\n" in text
    assert "    virtualenv_install_with_resources\n" in text


def test_refuses_a_third_party_package_under_the_minimum_age(tmp_path: Path) -> None:
    _pypi(tmp_path, "fresh-pkg", "1.0", uploaded=_YOUNG)
    proc, formula, before = _run(tmp_path, [("fresh-pkg", "1.0")])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "fresh-pkg==1.0: third-party" in proc.stderr
    assert formula.read_bytes() == before


def test_refuses_a_package_without_an_sdist(tmp_path: Path) -> None:
    _pypi(tmp_path, "wheel-only", "1.0", uploaded=_OLD, sdist=False)
    proc, formula, before = _run(tmp_path, [("wheel-only", "1.0")])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "no sdist" in proc.stderr
    assert formula.read_bytes() == before


def test_a_second_run_replaces_the_blocks_it_wrote(tmp_path: Path) -> None:
    _pypi(tmp_path, "alpha-pkg", "2.0", uploaded=_OLD)
    _pypi(tmp_path, "beta-pkg", "3.0", uploaded=_OLD)
    proc, formula, _ = _run(tmp_path, [("alpha-pkg", "2.0")])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    proc, formula, _ = _run(tmp_path, [("alpha-pkg", "2.0"), ("beta-pkg", "3.0")])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    first = formula.read_bytes()
    assert first.count(b'  resource "') == 2
    proc, formula, before = _run(tmp_path, [("alpha-pkg", "2.0"), ("beta-pkg", "3.0")])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert before == first == formula.read_bytes()


def test_refuses_a_formula_with_neither_marker_nor_blocks(tmp_path: Path) -> None:
    _pypi(tmp_path, "alpha-pkg", "2.0", uploaded=_OLD)
    bare = tmp_path / "bare.rb"
    bare.write_text("class Opencomplai < Formula\nend\n", encoding="utf-8")
    proc, formula, before = _run(tmp_path, [("alpha-pkg", "2.0")], formula=bare)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert formula.read_bytes() == before
