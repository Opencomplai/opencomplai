"""Behaviour guards for scripts/homebrew-release.sh (file URLs only, no network)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "homebrew-release.sh"
_FORMULA = _ROOT / "packaging" / "homebrew" / "opencomplai.rb"
_BASH = shutil.which("bash")
_V = "9.9.9"
_SDIST = b"stub sdist for the homebrew release test"
_GOOD = hashlib.sha256(_SDIST).hexdigest()

pytestmark = pytest.mark.skipif(_BASH is None, reason="bash not available")


def _run(
    tmp_path: Path,
    *,
    digest: str | None = None,
    entries: list[dict] | None = None,
    json_version: str = _V,
    args: list[str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path, bytes]:
    formula = tmp_path / "opencomplai.rb"
    if not formula.exists():
        formula.write_bytes(_FORMULA.read_bytes())
    before = formula.read_bytes()
    (tmp_path / f"opencomplai-{_V}.tar.gz").write_bytes(_SDIST)
    if entries is None:
        entries = [
            {
                "packagetype": "bdist_wheel",
                "filename": f"opencomplai-{_V}-py3-none-any.whl",
                "digests": {"sha256": "a" * 64},
            },
            {
                "packagetype": "sdist",
                "filename": f"opencomplai-{_V}.tar.gz",
                "digests": {"sha256": digest or _GOOD},
            },
        ]
    meta = tmp_path / "release.json"
    meta.write_text(
        json.dumps({"info": {"version": json_version}, "urls": entries}),
        encoding="utf-8",
    )
    env = {
        "PATH": str(Path(_BASH).parent) + os.pathsep + os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "HOMEBREW_PYPI_JSON_URL": meta.as_uri(),
        "HOMEBREW_SDIST_BASE_URL": tmp_path.as_uri(),
        "HOMEBREW_PYTHON": sys.executable,
    }
    cmd = [_BASH, str(_SCRIPT), *(args if args is not None else [_V])]
    if args is None:
        cmd += ["--formula", formula.as_posix()]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    return proc, formula, before


def _refused(
    proc: subprocess.CompletedProcess[str], formula: Path, before: bytes, step: str
) -> None:
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert f"HOMEBREW FAIL step={step}" in proc.stderr
    assert formula.read_bytes() == before


def test_patches_url_and_sha256_from_pypi_json(tmp_path: Path) -> None:
    proc, formula, before = _run(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"HOMEBREW PASS opencomplai=={_V} sha256={_GOOD}" in proc.stdout
    old = before.decode("utf-8").splitlines(keepends=True)
    new = formula.read_bytes().decode("utf-8").splitlines(keepends=True)
    expect = []
    for ln in old:
        if ln.lstrip().startswith("# PLACEHOLDER:"):
            continue
        if ln.lstrip().startswith("url "):
            ln = (
                '  url "https://files.pythonhosted.org/packages/source/o/opencomplai/'
                f'opencomplai-{_V}.tar.gz"\n'
            )
        elif ln.lstrip().startswith("sha256 "):
            ln = f'  sha256 "{_GOOD}"\n'
        expect.append(ln)
    assert new == expect


# A synthetic blake2b_256 digest and the PyPI path derived from it (2/2/60 split).
_B2 = "aabb" + "cc" * 30
_HASHED = (
    f"https://files.pythonhosted.org/packages/aa/bb/{'cc' * 30}/opencomplai-{_V}.tar.gz"
)


def _hashed_entry(**over: object) -> list[dict]:
    entry = {
        "packagetype": "sdist",
        "filename": f"opencomplai-{_V}.tar.gz",
        "url": _HASHED,
        "digests": {"sha256": _GOOD, "blake2b_256": _B2},
    }
    entry.update(over)
    return [entry]


def test_uses_the_hashed_source_url_from_the_release_json(tmp_path: Path) -> None:
    proc, formula, _ = _run(tmp_path, entries=_hashed_entry())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f'  url "{_HASHED}"\n' in formula.read_text(encoding="utf-8")


def test_second_run_with_a_hashed_url_is_idempotent(tmp_path: Path) -> None:
    proc, formula, _ = _run(tmp_path, entries=_hashed_entry())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    first = formula.read_bytes()
    proc, formula, before = _run(tmp_path, entries=_hashed_entry())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert before == first
    assert formula.read_bytes() == first


def test_refuses_a_url_whose_path_disagrees_with_blake2b_256(tmp_path: Path) -> None:
    other = _HASHED.replace("/aa/bb/", "/aa/bc/")
    _refused(*_run(tmp_path, entries=_hashed_entry(url=other)), "index")


def test_a_url_with_no_blake2b_digest_still_passes_the_shape_check(
    tmp_path: Path,
) -> None:
    entries = _hashed_entry(digests={"sha256": _GOOD})
    proc, formula, _ = _run(tmp_path, entries=entries)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f'  url "{_HASHED}"\n' in formula.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://example.com/packages/30/f9/abc123/opencomplai-9.9.9.tar.gz",
        "https://files.pythonhosted.org/packages/30/f9/abc123/other-9.9.9.tar.gz",
        'https://files.pythonhosted.org/packages/30/f9/abc123/opencomplai-9.9.9.tar.gz"\n',
        "http://files.pythonhosted.org/packages/30/f9/abc123/opencomplai-9.9.9.tar.gz",
        "https://files.pythonhosted.org/packages/30/F9/abc123/opencomplai-9.9.9.tar.gz",
        "https://files.pythonhosted.org/packages/30/f9/abc123/opencomplai-9.9.9.tar.gz?x=1",
        "https://files.pythonhosted.org/packages/30/f9/abc123/opencomplai-9.9.9.tar.gz#frag",
        "https://files.pythonhosted.org/packages/30/f9/abc/123/opencomplai-9.9.9.tar.gz",
        "https://files.pythonhosted.org/packages/30/f9/abc123/../opencomplai-9.9.9.tar.gz",
    ],
)
def test_refuses_an_sdist_url_that_is_not_a_pypi_files_url(
    tmp_path: Path, bad_url: str
) -> None:
    entries = [
        {
            "packagetype": "sdist",
            "filename": f"opencomplai-{_V}.tar.gz",
            "url": bad_url,
            "digests": {"sha256": _GOOD},
        }
    ]
    _refused(*_run(tmp_path, entries=entries), "index")


def test_refuses_download_that_does_not_match_digest(tmp_path: Path) -> None:
    other = hashlib.sha256(b"different bytes").hexdigest()
    _refused(*_run(tmp_path, digest=other), "download")


def test_refuses_all_zero_placeholder_digest(tmp_path: Path) -> None:
    proc, formula, before = _run(tmp_path, digest="0" * 64)
    _refused(proc, formula, before, "digest")
    assert "placeholder" in proc.stderr


def test_refuses_json_without_sdist(tmp_path: Path) -> None:
    wheel = [{"packagetype": "bdist_wheel", "digests": {"sha256": _GOOD}}]
    _refused(*_run(tmp_path, entries=wheel), "index")
    two = [{"packagetype": "sdist", "digests": {"sha256": _GOOD}}] * 2
    _refused(*_run(tmp_path, entries=two), "index")


def test_refuses_json_version_mismatch(tmp_path: Path) -> None:
    _refused(*_run(tmp_path, json_version="1.0.0"), "index")


def test_bad_version_argument_exits_2(tmp_path: Path) -> None:
    for args in (["1.2"], ["v1.2.3"], []):
        proc, formula, before = _run(tmp_path, args=args)
        assert proc.returncode == 2, proc.stdout + proc.stderr
        assert "usage" in proc.stderr
        assert formula.read_bytes() == before


def test_second_run_is_idempotent(tmp_path: Path) -> None:
    proc, formula, _ = _run(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    first = formula.read_bytes()
    proc, formula, before = _run(tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert before == first
    assert formula.read_bytes() == first


def test_script_parses_with_bash_n() -> None:
    proc = subprocess.run(
        [_BASH, "-n", str(_SCRIPT)], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr


def test_default_formula_path_and_static_guards() -> None:
    text = _SCRIPT.read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    assert "set -euo pipefail" in code
    assert "packaging/homebrew/opencomplai.rb" in code
    assert "sudo" not in code
    assert "| sh" not in code
    assert not re.search(r"\bgh\b", code)
    assert not re.search(r"\bgit\b", code)
    # The committed formula is untouched: the test run never wrote it.
    assert f'sha256 "{"0" * 64}"' in _FORMULA.read_text(encoding="utf-8")
