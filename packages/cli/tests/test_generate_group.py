"""The `generate` group: module discovery and the shared failure helper."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from opencomplai_cli.commands import generate
from typer.testing import CliRunner


def _make_package(root: Path, name: str, files: dict[str, str]) -> None:
    pkg = root / name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    for fname, body in files.items():
        (pkg / fname).write_text(body)


def test_help_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    # Typer needs two commands to keep the group level (one collapses into the
    # command itself) and no generator module may exist yet: register two probe
    # commands on a copy of the list.
    monkeypatch.setattr(
        generate.app, "registered_commands", list(generate.app.registered_commands)
    )

    @generate.app.command("probe-a")
    def _probe_a() -> None:
        """Probe."""

    @generate.app.command("probe-b")
    def _probe_b() -> None:
        """Probe."""

    result = CliRunner().invoke(generate.app, ["--help"])
    assert result.exit_code == 0
    assert "Generate documents and exports" in result.output


def test_discover_imports_only_gen_modules_in_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_package(
        tmp_path,
        "pkg_ok",
        {"gen_b.py": "", "gen_a.py": "", "other.py": ""},
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    import pkg_ok

    try:
        assert generate.discover(pkg_ok) == ["pkg_ok.gen_a", "pkg_ok.gen_b"]
        assert "pkg_ok.other" not in sys.modules
    finally:
        for mod in [m for m in sys.modules if m.startswith("pkg_ok")]:
            del sys.modules[mod]


def test_discover_raises_on_broken_generator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_package(tmp_path, "pkg_bad", {"gen_x.py": "raise RuntimeError('boom')\n"})
    monkeypatch.syspath_prepend(str(tmp_path))
    import pkg_bad

    try:
        with pytest.raises(RuntimeError, match="boom"):
            generate.discover(pkg_bad)
    finally:
        for mod in [m for m in sys.modules if m.startswith("pkg_bad")]:
            del sys.modules[mod]


def test_fail_exits_two() -> None:
    with pytest.raises(SystemExit) as exc:
        generate.fail("x")
    assert exc.value.code == 2
