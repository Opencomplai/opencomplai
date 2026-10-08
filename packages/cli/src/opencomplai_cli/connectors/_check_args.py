"""Build the extra ``opencomplai check`` arguments for the CI connectors."""

from __future__ import annotations

import shlex
from collections.abc import Mapping

_SHA_VARS = ("GITHUB_SHA", "CI_COMMIT_SHA")


def build_check_args(
    check_args: list[str] | None,
    env: Mapping[str, str],
    argv: list[str] | None = None,
) -> list[str]:
    """OPENCOMPLAI_CHECK_ARGS, then ``check_args``, then ``argv`` (later wins).

    Adds ``--commit-ref <CI SHA>`` when none was given. A malformed
    OPENCOMPLAI_CHECK_ARGS raises ``ValueError``.
    """
    result = shlex.split(env.get("OPENCOMPLAI_CHECK_ARGS", ""))
    result += list(check_args or []) + list(argv or [])
    if not any(t == "--commit-ref" or t.startswith("--commit-ref=") for t in result):
        for var in _SHA_VARS:
            sha = env.get(var, "")
            if len(sha) >= 7:
                result += ["--commit-ref", sha]
                break
    return result
