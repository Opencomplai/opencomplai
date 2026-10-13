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
import yaml

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


# --- Reverse guard: every real option of a documented command is named ---------

_ACTION_YML = _ROOT / "integrations" / "github-action" / "action.yml"
_ACTION_PAGE = _ROOT / "docs" / "src" / "guides" / "github-action.md"

# For these the option must sit in the first cell of a table row, so deleting
# its row fails. Every other command with a page only needs the name in a code
# span, as the forward guard does.
_STRICT = {"check", "agents"}

# ratchet: stays empty. Every real option of a non-strict command is named on its
# page. A new entry needs an epic that documents the option first; the stale-entry
# test fails when one is documented but still listed.
_KNOWN_UNDOCUMENTED: dict[str, set[str]] = {}

# The 19 options this ratchet listed before the pages documented them. The guards
# below keep them pinned to real options and to their pages.
_FORMERLY_UNDOCUMENTED: dict[str, set[str]] = {
    "checker": {"--local"},
    "dashboard": {"--local-only"},
    "docs": {"--manifest", "--no-push", "--push"},
    "gaps": {"--sort", "--strict"},
    "incident": {"--closed-at", "--party-kind", "--ref"},
    "init": {"--repo-root", "--scan"},
    "recommend": {"--sort"},
    "report": {"--sort"},
    "scan": {
        "--ai-deep",
        "--ai-verbose",
        "--no-emit-evidence",
        "--no-enqueue-review",
        "--strict",
    },
}

_TABLE_ROW_RE = re.compile(r"^\|([^|]*)\|")


def _table_options(text: str) -> set[str]:
    """Options named in the first cell of a Markdown table row."""
    found: set[str] = set()
    for line in text.splitlines():
        match = _TABLE_ROW_RE.match(line)
        if match:
            found |= set(_OPTION_RE.findall(match.group(1)))
    return found


def _command_pages(name: str, command) -> list[Path]:
    paths = [_CLI_DOCS / f"{_ALIAS.get(name, name)}.md"]
    if hasattr(command, "commands"):  # a group may use `<name>-<sub>.md` pages
        paths += sorted(_CLI_DOCS.glob(f"{name}-*.md"))
    return [p for p in paths if p.exists()]


def _real_options(command) -> set[str]:
    """Long option names of a command and, for a group, its subcommands."""
    names: set[str] = set()
    for param in command.params:
        if getattr(param, "hidden", False):
            continue
        names.update(
            o
            for o in (
                *getattr(param, "opts", []),
                *getattr(param, "secondary_opts", []),
            )
            if o.startswith("--")
        )
    for sub in getattr(command, "commands", {}).values():
        if not getattr(sub, "hidden", False):
            names |= _real_options(sub)
    return names - {"--help"}


def _documented_commands():
    """(name, command, page text) for every visible command that has a page."""
    click_app = typer.main.get_command(app)
    for name, command in sorted(click_app.commands.items()):
        if getattr(command, "hidden", False):
            continue
        pages = _command_pages(name, command)
        if pages:
            text = "\n".join(p.read_text(encoding="utf-8") for p in pages)
            yield name, command, text


def _named(name: str, text: str) -> set[str]:
    if name in _STRICT:
        return _table_options(text)
    return set(_OPTION_RE.findall(text))


def test_pages_name_every_real_option():
    seen = set()
    unnamed: dict[str, list[str]] = {}
    for name, command, text in _documented_commands():
        seen.add(name)
        gap = (
            _real_options(command)
            - _named(name, text)
            - _KNOWN_UNDOCUMENTED.get(name, set())
        )
        if gap:
            unnamed[name] = sorted(gap)
    assert _STRICT <= seen, "a strict command lost its page: the guard is vacuous"
    assert not unnamed, f"real options named on no page (or in no table row): {unnamed}"


def test_known_undocumented_entries_are_real_and_still_missing():
    documented = {name: (cmd, text) for name, cmd, text in _documented_commands()}
    problems: list[str] = []
    for name, options in _KNOWN_UNDOCUMENTED.items():
        if name in _STRICT or name not in documented:
            problems.append(f"{name}: not a non-strict command with a page")
            continue
        command, text = documented[name]
        problems += [
            f"{name} {opt}: not a real option"
            for opt in options - _real_options(command)
        ]
        problems += [
            f"{name} {opt}: now documented, remove it from _KNOWN_UNDOCUMENTED"
            for opt in options & _named(name, text)
        ]
    assert not problems, problems


def test_known_undocumented_list_is_empty():
    assert not _KNOWN_UNDOCUMENTED


def test_formerly_undocumented_options_are_real_and_documented():
    documented = {name: (cmd, text) for name, cmd, text in _documented_commands()}
    for name, options in _FORMERLY_UNDOCUMENTED.items():
        assert name in documented, f"{name}: no page for this command"
        command, text = documented[name]
        real = _real_options(command)
        assert options <= real, f"{name}: not real options {sorted(options - real)}"
        named = _named(name, text)
        assert options <= named, (
            f"{name}: not named on its page {sorted(options - named)}"
        )


_ROW_CELLS_RE = re.compile(r"^\|([^|]*)\|([^|]*)\|")


def test_new_option_rows_state_the_real_default():
    # (command, option) -> the second cell the table row must state, exactly.
    wanted = {
        ("gaps", "--sort"): "`article`",
        ("recommend", "--sort"): "`article`",
        ("report", "--sort"): "`article`",
        ("init", "--repo-root"): "`.`",
        ("init", "--scan"): "`False`",
        ("scan", "--strict"): "off",
        ("scan", "--ai-deep"): "off",
        ("scan", "--ai-verbose"): "off",
        ("scan", "--no-enqueue-review"): "off",
        ("scan", "--no-emit-evidence"): "on",
        ("gaps", "--strict"): "off",
        ("docs", "--push"): "`--no-push`",
        ("docs", "--manifest"): "*(none)*",
        ("dashboard", "--local-only"): "off",
    }
    texts = {name: text for name, _cmd, text in _documented_commands()}
    for (name, option), token in wanted.items():
        assert name in texts, f"{name}: no page for this command"
        cells = [
            m.group(2).strip()
            for line in texts[name].splitlines()
            if (m := _ROW_CELLS_RE.match(line)) and f"`{option}`" in m.group(1)
        ]
        assert cells, f"{name} {option}: no table row names it"
        assert cells[0] == token, (
            f"{name} {option}: default cell is {cells[0]!r}, expected {token!r}"
        )


def test_check_page_guard_fails_when_any_option_row_is_removed():
    click_app = typer.main.get_command(app)
    real = _real_options(click_app.commands["check"])
    lines = (_CLI_DOCS / "check.md").read_text(encoding="utf-8").splitlines()
    assert not real - _table_options("\n".join(lines)), "check.md already has a gap"
    tried = 0
    for i, line in enumerate(lines):
        row = _table_options(line)
        if not row:
            continue
        without = "\n".join(lines[:i] + lines[i + 1 :])
        missing = real - _table_options(without)
        assert missing, f"removing row {line[:40]!r} went unnoticed"
        assert row <= missing, (
            f"removing row {line[:40]!r} did not fail for its options"
        )
        tried += 1
    assert tried >= 20, f"only {tried} option rows found in check.md"


def test_check_args_variable_is_documented():
    pages = [_CLI_DOCS / "check.md", _ACTION_PAGE]
    missing = [
        p.name
        for p in pages
        if "OPENCOMPLAI_CHECK_ARGS" not in p.read_text(encoding="utf-8")
    ]
    assert not missing, f"OPENCOMPLAI_CHECK_ARGS not documented on: {missing}"


def test_github_action_page_names_every_input_and_output():
    spec = yaml.safe_load(_ACTION_YML.read_text(encoding="utf-8"))
    wanted = [*spec["inputs"], *spec["outputs"]]
    assert len(wanted) >= 10, "action.yml lost its inputs or outputs"
    cells = [
        m.group(1)
        for line in _ACTION_PAGE.read_text(encoding="utf-8").splitlines()
        if (m := _TABLE_ROW_RE.match(line))
    ]
    missing = [k for k in wanted if not any(f"`{k}`" in c for c in cells)]
    assert not missing, f"github-action.md has no table row for: {missing}"


def test_github_action_page_is_in_nav():
    assert "guides/github-action.md" in _nav()


def test_scan_page_documents_propose_wording_and_ai_plugin():
    text = (_CLI_DOCS / "scan.md").read_text(encoding="utf-8")
    assert "`--propose`" in text
    assert "suggests a classification from your code" in text
    assert "optional AI plugin" in text
    # The install hint is whatever `_require_ai_plugin` prints; read it from the source.
    source = (_SRC / "main.py").read_text(encoding="utf-8")
    hint = re.search(r"Basic:\s+(pip install [\w-]+)", source)
    assert hint, "main.py lost the install hint printed by _require_ai_plugin"
    assert hint.group(1) in text
