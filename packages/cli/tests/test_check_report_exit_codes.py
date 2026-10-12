"""Exit codes 2, 3 and 4 of `check` survive the report flags; reports follow a completed check.

Each case is its own test: a halt written by exit 4 must never leak into another case.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .test_golden_eu_output import CHATBOT, _init
from .test_golden_eu_output import cli as golden_cli  # noqa: F401  (fixture)

SOCIAL_SCORING = "social scoring system for citizen behaviour ranking"
REPORT_FLAGS = [
    "--report-junit",
    "r.xml",
    "--sarif-output",
    "r.sarif",
    "--summary-md",
    "r.md",
]
REPORT_FILES = ("r.xml", "r.sarif", "r.md")


@pytest.fixture
def cli(request):
    return request.getfixturevalue("golden_cli")


def _check(cli, case: int, flags: list[str]) -> None:
    """Run `check` for one case: 2 no manifest, 3 prohibited purpose, 4 halt trap."""
    if case == 3:
        _init(cli, SOCIAL_SCORING)
    elif case == 4:
        _init(cli, CHATBOT)
    extra = ["--change-context", "model_retrain"] if case == 4 else []
    cli("check", *extra, *flags, exit_code=case)


@pytest.mark.parametrize("case", [2, 3, 4])
@pytest.mark.parametrize("with_flags", [False, True])
def test_exit_code_unchanged_by_report_flags(cli, case, with_flags):
    flags = REPORT_FLAGS if with_flags else []
    _check(cli, case, flags)


@pytest.mark.parametrize("case", [3, 4])
def test_reports_written_for_exits_3_and_4(cli, case):
    _check(cli, case, REPORT_FLAGS)
    for name in REPORT_FILES:
        path = Path(name)
        assert path.is_file(), name
        assert path.stat().st_size > 0, name


def test_no_reports_written_for_exit_2(cli):
    _check(cli, 2, REPORT_FLAGS)
    assert not any(Path(name).exists() for name in REPORT_FILES)
