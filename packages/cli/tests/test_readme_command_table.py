"""
DG-11: guard against the exact rot this epic fixes -- README's "Core
commands" table silently drifting out of sync with the real CLI (it used to
omit `push` entirely and advertise `dashboard` as a working command when its
only real entry point, `enroll`, had no working way to obtain a bootstrap
token).

Scope note: "top-level command" here means a flat command registered
directly on the top-level typer `app` (`app.registered_commands` -- e.g.
`init`, `scan`, `push`), not a command *group* reached via `add_typer`
(`docs`, `risk`, `sync`, `dashboard`, `keys`, `ai`, `controls`). A group
needs a second word to do anything (`opencomplai docs generate`), so it
isn't itself an invocable command the way a flat one is, and the README's
own "Core commands" table has never tried to enumerate groups -- it names
them in prose instead (see the paragraph right after the table). This is
also what makes DG-11's task 3 ("remove the `dashboard` README row") and
this completeness check consistent with each other: `dashboard` is a group,
so its removal from the table doesn't leave a flat command undocumented.
"""

from __future__ import annotations

import re
from pathlib import Path

from opencomplai_cli.main import app

_README = Path(__file__).resolve().parents[1] / "README.md"

_ROW_RE = re.compile(r"^\|\s*`opencomplai ([a-zA-Z0-9_-]+)`\s*\|", re.MULTILINE)


def _readme_table_commands() -> set[str]:
    text = _README.read_text(encoding="utf-8")
    return set(_ROW_RE.findall(text))


def _registered_flat_commands(hidden: bool = False) -> set[str]:
    return {c.name for c in app.registered_commands if bool(c.hidden) == hidden}


def test_readme_exists():
    assert _README.exists(), f"missing {_README}"


def test_every_non_hidden_top_level_command_appears_in_readme_table():
    table_commands = _readme_table_commands()
    non_hidden = _registered_flat_commands(hidden=False)
    missing = non_hidden - table_commands
    assert not missing, (
        f"commands registered on the CLI but missing from README's command "
        f"table: {sorted(missing)}"
    )


def test_readme_table_has_no_fictional_commands():
    table_commands = _readme_table_commands()
    real = {c.name for c in app.registered_commands}
    fictional = table_commands - real
    assert not fictional, f"README lists commands that don't exist: {sorted(fictional)}"


def test_hidden_commands_are_not_promoted_in_readme_table():
    table_commands = _readme_table_commands()
    hidden = _registered_flat_commands(hidden=True)
    leaked = table_commands & hidden
    assert not leaked, f"README promotes hidden command(s): {sorted(leaked)}"


def test_readme_push_row_present():
    """The specific regression DG-11 fixes: `push` existed in the CLI but
    was entirely missing from the table."""
    assert "push" in _readme_table_commands()


def test_readme_no_bare_dashboard_row():
    """`dashboard`'s only historically-advertised entry point (`enroll`) has
    no working way to obtain a bootstrap token -- the README must not
    promote it as a working command (DG-11 task 3)."""
    assert "dashboard" not in _readme_table_commands()
