"""Flags reach ``opencomplai check`` through both CI connectors."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from opencomplai_cli.connectors import github_actions, gitlab_ci

BASE = ["opencomplai", "check", "--sign-if-available"]
FLAGS = [
    "--scan",
    "--fail-on",
    "high",
    "--with-gaps",
    "--change-context",
    "model_retrain",
]


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    for v in (
        "GITHUB_SHA",
        "CI_COMMIT_SHA",
        "OPENCOMPLAI_CHECK_ARGS",
        "SIGNING_KEY_PRIVATE",
    ):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.chdir(tmp_path)


def _run(mod, env=None, argv=None):
    """Run the connector; return (rc, command or None)."""
    kw = {"junit_path": os.devnull} if mod is gitlab_ci else {}
    with patch(
        "subprocess.run", return_value=MagicMock(stdout="", stderr="", returncode=0)
    ) as m:
        rc = mod.run_connector(env=env or {}, argv=argv, **kw)
    return rc, (m.call_args[0][0] if m.called else None)


MODS = [github_actions, gitlab_ci]


def _contig(cmd, sub):
    return any(cmd[i : i + len(sub)] == sub for i in range(len(cmd)))


def test_argv_flags_reach_check_gha():
    _, cmd = _run(github_actions, argv=FLAGS)
    assert cmd[: len(BASE)] == BASE
    assert _contig(cmd[len(BASE) :], FLAGS)


def test_argv_flags_reach_check_gitlab():
    _, cmd = _run(gitlab_ci, argv=FLAGS)
    assert cmd[: len(BASE)] == BASE
    assert _contig(cmd[len(BASE) :], FLAGS)


@pytest.mark.parametrize("mod", MODS)
def test_env_args_then_argv_order(mod):
    _, cmd = _run(
        mod,
        env={"OPENCOMPLAI_CHECK_ARGS": "--fail-on low --with-gaps"},
        argv=["--fail-on", "high"],
    )
    assert cmd[len(BASE) :] == ["--fail-on", "low", "--with-gaps", "--fail-on", "high"]


def test_commit_ref_defaults_to_ci_sha():
    _, cmd = _run(github_actions, env={"GITHUB_SHA": "a" * 40})
    assert cmd[-2:] == ["--commit-ref", "a" * 40]
    _, cmd = _run(gitlab_ci, env={"CI_COMMIT_SHA": "b" * 40})
    assert cmd[-2:] == ["--commit-ref", "b" * 40]
    _, cmd = _run(github_actions, env={"GITHUB_SHA": "abc12"})
    assert "--commit-ref" not in cmd


@pytest.mark.parametrize("mod", MODS)
def test_explicit_commit_ref_wins(mod):
    sha = {"GITHUB_SHA": "a" * 40, "CI_COMMIT_SHA": "b" * 40}
    for env, argv in (
        (sha, ["--commit-ref", "abc1234"]),
        (sha, ["--commit-ref=abc1234"]),
        ({**sha, "OPENCOMPLAI_CHECK_ARGS": "--commit-ref abc1234"}, None),
    ):
        _, cmd = _run(mod, env=env, argv=argv)
        refs = [t for t in cmd if t.startswith("--commit-ref")]
        assert len(refs) == 1
        assert "a" * 40 not in cmd
        assert "b" * 40 not in cmd


@pytest.mark.parametrize("mod", MODS)
def test_no_args_no_sha_keeps_base_command(mod):
    _, cmd = _run(mod)
    assert cmd == BASE


@pytest.mark.parametrize("mod", MODS)
def test_bad_check_args_quote_returns_2(mod):
    rc, cmd = _run(mod, env={"OPENCOMPLAI_CHECK_ARGS": '--x "'})
    assert rc == 2
    assert cmd is None
