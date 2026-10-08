"""Every command and group has a CLI reference page, a nav entry and a README mention.

Strict mkdocs does not fail on a page missing from the nav, and nothing stopped a
command from shipping without a page, so this guard does. It also checks that the
option names on the hand-written pages exist in the live app, and that every kind
registered with `opencomplai verify` has a row in the verify page's Kinds table.
"""

from __future__ import annotations

import re
from pathlib import Path

import typer.main

# Importing main registers every command and every verify kind.
from opencomplai_cli.main import app

_ROOT = Path(__file__).resolve().parents[3]
_CLI_DOCS = _ROOT / "docs" / "src" / "cli"
_MKDOCS = _ROOT / "docs" / "mkdocs.yml"
_README = _ROOT / "packages" / "cli" / "README.md"
_SRC = _ROOT / "packages" / "cli" / "src" / "opencomplai_cli"

# Commands that share a page.
_ALIAS = {"approve": "approve-resume", "resume": "approve-resume", "version": "info"}

# Page stem -> the command or group names whose options the page may name.
_PAGE_COMMANDS = {
    "push": ["push"],
    "approve-resume": ["approve", "resume"],
    "keys": ["keys"],
    "ai": ["ai"],
    "info": ["info", "version"],
    "deployer-pack": ["deployer-pack"],
    "portfolio": ["check"],
}


def _name(info) -> str:
    return info.name or info.callback.__name__.replace("_", "-")


def _flat() -> list[str]:
    return [_name(c) for c in app.registered_commands if not c.hidden]


def _groups() -> dict[str, list[str]]:
    return {
        g.name: [_name(c) for c in g.typer_instance.registered_commands if not c.hidden]
        for g in app.registered_groups
        if not g.hidden
    }


def _pages() -> set[str]:
    return {p.stem for p in _CLI_DOCS.glob("*.md")}


def _nav() -> str:
    return _MKDOCS.read_text(encoding="utf-8")


def _walk(typer_app, prefix=()):
    """Yield ("command"|"group", name_parts) for every visible command, recursing."""
    for c in typer_app.registered_commands:
        if not c.hidden:
            yield "command", (*prefix, _name(c))
    for g in typer_app.registered_groups:
        if not g.hidden:
            parts = (*prefix, g.name)
            yield "group", parts
            yield from _walk(g.typer_instance, parts)


def _missing_pages(typer_app, existing_stems) -> list[str]:
    """Names of commands/groups with no page. A group needs `g.md` or every child covered."""
    kinds = {parts: kind for kind, parts in _walk(typer_app)}

    def covered(parts) -> bool:
        if kinds[parts] == "command" and len(parts) == 1:
            return _ALIAS.get(parts[0], parts[0]) in existing_stems
        if "-".join(parts) in existing_stems:
            return True
        kids = [p for p in kinds if p[:-1] == parts]
        return kinds[parts] == "group" and bool(kids) and all(covered(k) for k in kids)

    return sorted(
        " ".join(parts) for parts in kinds if len(parts) == 1 and not covered(parts)
    )


def _nav_pages(mkdocs_text: str) -> set[str]:
    return set(re.findall(r"cli/[A-Za-z0-9_.-]+\.md", mkdocs_text))


def _missing_nav(page_names, mkdocs_text: str) -> list[str]:
    nav = _nav_pages(mkdocs_text)
    return sorted(n for n in page_names if f"cli/{n}" not in nav)


def test_every_command_and_group_has_a_cli_page():
    missing = _missing_pages(app, _pages())
    assert not missing, f"no docs/src/cli page for: {missing}"


def test_every_cli_page_is_in_nav():
    missing = _missing_nav([p.name for p in _CLI_DOCS.glob("*.md")], _nav())
    assert not missing, f"CLI pages missing from docs/mkdocs.yml nav: {missing}"


def _stems_without(*omit):
    return _pages() - set(omit)


def test_missing_page_is_reported():
    assert "push" in _pages(), "real tree lost push.md: test would be vacuous"
    assert _missing_pages(app, _stems_without("push")) == ["push"]


def test_group_satisfied_by_either_style():
    group = next(g for g in app.registered_groups if not g.hidden)
    subs = [_name(c) for c in group.typer_instance.registered_commands if not c.hidden]
    base = _pages() - {group.name} - {f"{group.name}-{s}" for s in subs}
    assert group.name in _missing_pages(app, base)
    assert group.name not in _missing_pages(
        app, base | {f"{group.name}-{s}" for s in subs}
    )
    if subs:
        partial = base | {f"{group.name}-{s}" for s in subs[1:]}
        assert group.name in _missing_pages(app, partial)
    assert group.name not in _missing_pages(app, base | {group.name})


def test_hidden_command_needs_no_page():
    stems = _pages() - {"dashboard-enroll", "enroll"}
    assert not any("enroll" in m for m in _missing_pages(app, stems))
    assert ("command", ("dashboard", "enroll")) not in set(_walk(app))


def test_missing_nav_entry_is_reported():
    text = "nav:\n  - init: cli/init.md\n"
    assert "cli/push.md" not in _nav_pages(text)
    assert _nav_pages(text) == {"cli/init.md"}
    assert _missing_nav(["init.md", "push.md"], text) == ["push.md"]


def test_every_group_named_in_readme():
    text = _README.read_text(encoding="utf-8")
    missing = [g for g in _groups() if f"`{g}`" not in text]
    assert not missing, f"command groups not named in packages/cli/README.md: {missing}"


def _option_names(command) -> set[str]:
    names: set[str] = set()
    for param in command.params:
        names.update(getattr(param, "opts", []))
        names.update(getattr(param, "secondary_opts", []))
    for sub in getattr(command, "commands", {}).values():
        names |= _option_names(sub)
    return names


_OPTION_RE = re.compile(r"(?<!`)`(--[a-z][a-z0-9-]*)")


def test_new_pages_name_real_options():
    click_app = typer.main.get_command(app)
    wrong: dict[str, list[str]] = {}
    for page, commands in _PAGE_COMMANDS.items():
        path = _CLI_DOCS / f"{page}.md"
        if not path.exists():  # a page for a feature absent at this tip
            continue
        real: set[str] = set()
        for name in commands:
            real |= _option_names(click_app.commands[name])
        named = set(_OPTION_RE.findall(path.read_text(encoding="utf-8")))
        if named - real - {"--help"}:
            wrong[page] = sorted(named - real - {"--help"})
    assert not wrong, f"pages name options the live commands do not have: {wrong}"


def _registered_kinds() -> set[str]:
    from opencomplai_cli.commands.verify import _KINDS

    pattern = re.compile(r"register_kind\(\s*[\"']([a-z0-9-]+)[\"']")
    found = set(_KINDS)
    for path in _SRC.rglob("*.py"):
        found |= set(pattern.findall(path.read_text(encoding="utf-8")))
    return found


def test_verify_kinds_table_lists_every_registered_kind():
    kinds = _registered_kinds()
    assert "artifact" in kinds, "registry is empty: the check would be vacuous"
    lines = (_CLI_DOCS / "verify.md").read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if re.match(r"^#+\s+Kinds\s*$", ln))
    rows: set[str] = set()
    for ln in lines[start + 1 :]:
        if ln.startswith("#"):
            break
        match = re.match(r"^\|\s*`([a-z0-9-]+)`\s*\|", ln)
        if match:
            rows.add(match.group(1))
    missing = sorted(kinds - rows)
    assert not missing, f"verify.md Kinds table has no row for: {missing}"
