"""The documented strict reading must equal the strict block of run.sh.

Pure file reads. The two CI guides and the GitHub Action script carry the same
five-flag set; a change to one flag (or the fail-on value) without the others fails here.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_RUN_SH = _ROOT / "integrations" / "github-action" / "run.sh"
_GITLAB_AZURE = _ROOT / "docs" / "src" / "guides" / "ci-gitlab-azure.md"
_RECIPES = _ROOT / "docs" / "src" / "guides" / "ci-recipes.md"
_HEADING = "## Strict reading"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _flags(tokens: list[str]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for i, tok in enumerate(tokens):
        if tok.startswith("--"):
            nxt = tokens[i + 1] if i + 1 < len(tokens) else None
            out[tok] = nxt if nxt is not None and not nxt.startswith("--") else None
    return out


def _run_sh_strict_flags() -> dict[str, str | None]:
    src = _text(_RUN_SH)
    m = re.search(
        r'if \[ "\$\{OC_STRICT:-false\}" = true \]; then\n(.*?)\nfi\n', src, re.S
    )
    assert m, "OC_STRICT block not found in run.sh"
    tokens: list[str] = []
    for grp in re.findall(r"cmd\+=\(([^)]*)\)", m.group(1)):
        tokens += shlex.split(grp)
    return _flags(tokens)


def _section(page: str) -> str:
    i = page.index(_HEADING)
    m = re.search(r"^## ", page[i + len(_HEADING) :], re.M)
    return page[i : i + len(_HEADING) + m.start()] if m else page[i:]


def _bash_blocks(section: str) -> list[str]:
    return re.findall(r"```bash\n(.*?)```", section, re.S)


def _documented_flags(page: str) -> dict[str, str | None]:
    block = _bash_blocks(_section(page))[0].replace("\\n", " ").strip()
    value = block.split("=", 1)[1]
    return _flags(shlex.split(" ".join(shlex.split(value))))


_STRICT = (
    "--with-gaps --scan --fail-on major --require-exemption-record --sign-if-available"
)


def _from_string(s: str) -> dict[str, str | None]:
    return _flags(shlex.split(s))


def test_run_sh_strict_block_found_nontrivial() -> None:
    flags = _run_sh_strict_flags()
    assert {
        "--with-gaps",
        "--scan",
        "--fail-on",
        "--require-exemption-record",
        "--sign-if-available",
    } <= set(flags)
    assert flags["--fail-on"] == "major"


def test_gitlab_azure_page_has_strict_reading_section() -> None:
    page = _text(_GITLAB_AZURE)
    assert _HEADING in page
    assert _documented_flags(page) == _run_sh_strict_flags()
    section = _section(page)
    for needle in ("OPENCOMPLAI_CHECK_ARGS", "extra_args", ".ocignore"):
        assert needle in section


def test_recipes_page_has_strict_reading_section() -> None:
    page = _text(_RECIPES)
    assert _HEADING in page
    assert page.index(_HEADING) < page.index("## Jenkins")
    assert _documented_flags(page) == _run_sh_strict_flags()
    assert "opencomplai==" not in _section(page)


def test_documented_flag_set_equals_run_sh_strict_block() -> None:
    a = _documented_flags(_text(_GITLAB_AZURE))
    b = _documented_flags(_text(_RECIPES))
    assert a == b == _run_sh_strict_flags()


def test_flag_set_comparison_detects_a_single_changed_flag() -> None:
    base = _from_string(_STRICT)
    assert base == _from_string(_STRICT)
    assert base != _from_string(_STRICT.replace("--scan ", ""))
    assert base != _from_string(
        _STRICT.replace("--fail-on major", "--fail-on critical")
    )
    assert base != _from_string(_STRICT + " --strict")


def test_secondary_snippets_stay_inside_the_canonical_set() -> None:
    section = _section(_text(_GITLAB_AZURE))
    canonical = set(_documented_flags(_text(_GITLAB_AZURE)))
    blocks = re.findall(r"```(?:bash|yaml)\n(.*?)```", section, re.S)[1:]
    assert blocks
    for block in blocks:
        used = set(re.findall(r"--[a-z][a-z-]*", block))
        assert used, block
        assert used <= canonical
        assert canonical - used <= {"--sign-if-available"}
