"""Per-pack golden snapshots of `gaps`, `check --gate` and `scope` output.

A pack card adds two directories and edits no shared test:
    packages/core/tests/fixtures/packs/<KEY>/   (fixture repos and manifest)
    packages/cli/tests/golden/packs/<KEY>/      (golden files)

A pack is discovered when its fixture directory has manifest.json. Layout and
update command: see the README files in both directories. Regenerate one
pack's goldens on purpose:
    OPENCOMPLAI_UPDATE_PACK_GOLDEN=<KEY> uv run pytest \
        packages/cli/tests/test_pack_goldens.py -k <KEY>
This is not the EU variable: the flat EU and NIST goldens are never rewritten.
"""

from __future__ import annotations

import io
import json
import os
import shutil
from pathlib import Path

import pytest
from opencomplai_cli import main
from opencomplai_core.frameworks import FRAMEWORKS, FrameworkPack
from opencomplai_core.models import FrameworkReport
from opencomplai_core.report_engine import render_framework_section
from rich.console import Console
from typer.testing import CliRunner

from .test_golden_eu_output import _normalise

FIXTURES = Path(__file__).resolve().parents[2] / "core" / "tests" / "fixtures" / "packs"
GOLDEN = Path(__file__).parent / "golden" / "packs"
UPDATE_ENV = "OPENCOMPLAI_UPDATE_PACK_GOLDEN"

TREES = ("empty", "scaffolded", "evidenced")
# Files `check` writes on the empty tree, and the golden each is compared with.
REPORT_FILES = (
    ("r.xml", "check_reports.junit.xml"),
    ("r.sarif", "check_reports.sarif.json"),
    ("r.md", "check_reports.summary.md"),
)


def discover(fixtures: Path | None = None) -> list[str]:
    """Keys of the packs whose fixture directory has a manifest.json."""
    base = FIXTURES if fixtures is None else fixtures
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if (p / "manifest.json").is_file())


def _golden_keys(golden: Path | None = None) -> list[str]:
    base = GOLDEN if golden is None else golden
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir())


def _applicability(key: str, fixtures: Path | None = None) -> list[str]:
    base = (FIXTURES if fixtures is None else fixtures) / key / "applicability"
    if not base.is_dir():
        return []
    return sorted(p.stem for p in base.glob("*.json"))


def update_command(key: str) -> str:
    return (
        f"{UPDATE_ENV}={key} uv run pytest "
        f"packages/cli/tests/test_pack_goldens.py -k {key}"
    )


def _cases() -> list[tuple[str, str]]:
    cases: list[tuple[str, str]] = []
    for key in discover():
        cases += [(key, f"gaps_{tree}") for tree in TREES]
        cases += [(key, "gate_empty"), (key, "check_reports")]
        cases.append((key, "report_section"))
        cases += [(key, f"applicability_{o}") for o in _applicability(key)]
    return cases


def _layout_keys() -> list[str]:
    return sorted(set(discover()) | set(_golden_keys()))


def _updating(key: str) -> bool:
    return os.environ.get(UPDATE_ENV) == key


def _assert_golden(
    golden: Path, key: str, name: str, text: str, *, update: bool
) -> None:
    path = golden / key / name
    if update:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return
    assert path.is_file(), f"missing {path}; run {update_command(key)}"
    assert text == path.read_text(encoding="utf-8"), (
        f"{key}/{name} drifted; if intended run {update_command(key)}"
    )


class _Runner:
    """Runs the CLI inside a temp copy of one fixture repo."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.tmp_path = tmp_path
        self.out = io.StringIO()
        self.monkeypatch = monkeypatch
        self.repo = tmp_path / "repo"
        for var in (
            "OPENCOMPLAI_API_URL",
            "OPENCOMPLAI_VAULT_URL",
            "OPENCOMPLAI_RISK_ENGINE_URL",
            "GITHUB_SHA",
            "CI_COMMIT_SHA",
        ):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
        monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))
        home = tmp_path / "home"
        monkeypatch.setattr(main, "_OPENCOMPLAI_DIR", home)
        monkeypatch.setattr(main, "_CONFIG_FILE", home / "config.yaml")
        monkeypatch.setattr(main, "_SIGNING_KEY", home / "signing.key")
        monkeypatch.setattr(main, "_SIGNING_PUB", home / "signing.pub")
        for name, buffer in (("console", self.out), ("err_console", io.StringIO())):
            monkeypatch.setattr(
                main,
                name,
                Console(
                    file=buffer, width=200, color_system=None, legacy_windows=False
                ),
            )

    def prepare(self, tree: Path | None, manifest: Path) -> None:
        if tree is None:
            self.repo.mkdir(parents=True)
        else:
            shutil.copytree(tree, self.repo)
        shutil.copyfile(manifest, self.repo / "system-manifest.json")
        self.monkeypatch.chdir(self.repo)

    def run(self, *args: str) -> tuple[int, str]:
        self.out.seek(0)
        self.out.truncate()
        result = CliRunner().invoke(main.app, list(args))
        assert not isinstance(result.exception, Exception) or isinstance(
            result.exception, SystemExit
        ), repr(result.exception)
        return result.exit_code, _normalise(
            self.out.getvalue() + result.output, self.tmp_path
        )


def run_case(
    key: str,
    name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    fixtures: Path | None = None,
    golden: Path | None = None,
    update: bool | None = None,
) -> None:
    """Run one case and compare (or, in update mode, write) its golden files."""
    fx = (FIXTURES if fixtures is None else fixtures) / key
    gd = GOLDEN if golden is None else golden
    upd = _updating(key) if update is None else update
    runner = _Runner(tmp_path, monkeypatch)

    def check(file: str, text: str) -> None:
        _assert_golden(gd, key, file, text, update=upd)

    if name.startswith("gaps_"):
        tree = fx / name.removeprefix("gaps_")
        assert tree.is_dir(), f"missing fixture repo {tree}"
        runner.prepare(tree, fx / "manifest.json")
        base = ("gaps", "--target", key, "--repo-root", ".")
        code, text = runner.run(*base, "--output", "json")
        assert code == 0, text
        check(f"{name}.json", text)
        code, text = runner.run(*base)
        assert code == 0, text
        check(f"{name}.txt", text)
    elif name == "report_section":
        runner.prepare(fx / "evidenced", fx / "manifest.json")
        code, text = runner.run(
            "gaps", "--target", key, "--repo-root", ".", "--output", "json"
        )
        assert code == 0, text
        envelope = json.loads(text)
        framework_report = FrameworkReport.model_validate(
            envelope["payload"]["frameworks"][key]
        )
        check("report_section.html", render_framework_section(framework_report) + "\n")
    elif name == "gate_empty":
        runner.prepare(fx / "empty", fx / "manifest.json")
        code, text = runner.run(
            "check",
            "--target",
            key,
            "--gate",
            key,
            "--gate-fail-on",
            "missing",
            "--repo-root",
            ".",
        )
        assert code in (0, 1), text
        artifact = json.loads(Path("compliance-artifact.json").read_text("utf-8"))
        failed = [c for c in artifact.get("failed_controls", []) if ":" in c]
        check(
            "gate_empty.txt", "".join(f"{line}\n" for line in [f"exit={code}", *failed])
        )
    elif name == "check_reports":
        runner.prepare(fx / "empty", fx / "manifest.json")
        code, text = runner.run(
            "check",
            "--target",
            key,
            "--gate",
            key,
            "--gate-fail-on",
            "missing",
            "--repo-root",
            ".",
            # Without --with-gaps the artifact carries no per-row verdicts.
            "--with-gaps",
            "--report-junit",
            "r.xml",
            "--sarif-output",
            "r.sarif",
            "--summary-md",
            "r.md",
        )
        assert code in (0, 1), text
        for written, golden_name in REPORT_FILES:
            raw = Path(written).read_bytes().decode("utf-8")
            check(golden_name, _normalise(raw, tmp_path))
    elif name.startswith("applicability_"):
        outcome = name.removeprefix("applicability_")
        runner.prepare(None, fx / "applicability" / f"{outcome}.json")
        code, text = runner.run("scope", key, "--output", "json")
        assert code == 0, text
        check(f"{name}.json", text)
    else:
        raise AssertionError(f"unknown case {name}")


def layout_problems(
    key: str, fixtures: Path | None = None, golden: Path | None = None, *, update: bool
) -> list[str]:
    fx = FIXTURES if fixtures is None else fixtures
    gd = GOLDEN if golden is None else golden
    problems = []
    if (
        (fx / key / "manifest.json").is_file()
        and not (gd / key).is_dir()
        and not update
    ):
        problems.append(
            f"pack {key} has fixtures but no golden directory {gd / key}; "
            f"run {update_command(key)}"
        )
    if (gd / key).is_dir() and not (fx / key / "manifest.json").is_file():
        problems.append(
            f"golden directory {gd / key} has no fixtures: expected {fx / key / 'manifest.json'}"
        )
    return problems


@pytest.mark.parametrize(("key", "name"), _cases(), ids=lambda v: str(v))
def test_pack_golden(key, name, tmp_path, monkeypatch):
    run_case(key, name, tmp_path, monkeypatch)


@pytest.mark.parametrize("key", _layout_keys())
def test_pack_layout(key):
    assert not layout_problems(key, update=_updating(key))


# --- self-test: the harness itself, on a pack built in tmp_path -------------

REQUIREMENTS = (
    Path(__file__).resolve().parents[2]
    / "core"
    / "tests"
    / "fixtures"
    / "framework_pack"
    / "requirements.json"
)
SELF_KEY = "FIXTURE"
RISK_REGISTER = (
    "# Risk register\n\nIdentified risks: biased scoring.\n"
    "Mitigation: quarterly fairness review; residual risk accepted.\n"
)


def _self_manifest(**extra: object) -> dict:
    return {
        "system_id": "pack-golden-sys",
        "intended_purpose": "customer support chatbot for an online shop",
        "compliance_target": "EU_AI_ACT",
        "compliance_targets": [SELF_KEY],
        "high_risk_presumption": False,
        "commit_ref": "HEAD",
        **extra,
    }


def _build_self_pack(root: Path) -> tuple[Path, Path]:
    fixtures, golden = root / "fixtures", root / "golden"
    pack = fixtures / SELF_KEY
    for tree in TREES:
        (pack / tree).mkdir(parents=True)
    (pack / "empty" / ".gitkeep").write_text("", encoding="utf-8")
    (pack / "scaffolded" / "docs").mkdir()
    (pack / "scaffolded" / "docs" / "risk_register.md").write_text("", encoding="utf-8")
    (pack / "evidenced" / "docs").mkdir()
    (pack / "evidenced" / "docs" / "risk_register.md").write_text(
        RISK_REGISTER, encoding="utf-8"
    )
    (pack / "manifest.json").write_text(json.dumps(_self_manifest()), encoding="utf-8")
    return fixtures, golden


@pytest.fixture
def self_pack(tmp_path, monkeypatch):
    monkeypatch.setitem(
        FRAMEWORKS,
        SELF_KEY,
        FrameworkPack(SELF_KEY, "Fixture framework", requirements=REQUIREMENTS),
    )
    fixtures, golden = _build_self_pack(tmp_path / "pack")
    return fixtures, golden, tmp_path / "runs"


def _self_names() -> list[str]:
    return [f"gaps_{t}" for t in TREES] + [
        "gate_empty",
        "check_reports",
        "report_section",
    ]


def _run_all(fixtures, golden, runs, monkeypatch, names, *, update):
    for i, name in enumerate(names):
        run_case(
            SELF_KEY,
            name,
            runs / f"{update}-{i}",
            monkeypatch,
            fixtures=fixtures,
            golden=golden,
            update=update,
        )


def test_update_then_compare_then_drift(self_pack, monkeypatch):
    fixtures, golden, runs = self_pack
    assert discover(fixtures) == [SELF_KEY]
    names = _self_names()

    _run_all(fixtures, golden, runs / "a", monkeypatch, names, update=True)
    files = sorted(p.name for p in (golden / SELF_KEY).iterdir())
    assert files == [
        "check_reports.junit.xml",
        "check_reports.sarif.json",
        "check_reports.summary.md",
        "gaps_empty.json",
        "gaps_empty.txt",
        "gaps_evidenced.json",
        "gaps_evidenced.txt",
        "gaps_scaffolded.json",
        "gaps_scaffolded.txt",
        "gate_empty.txt",
        "report_section.html",
    ]
    gate = (golden / SELF_KEY / "gate_empty.txt").read_text(encoding="utf-8")
    assert gate.splitlines()[0] == "exit=1"
    assert "FIXTURE:REQ-1" in gate.splitlines()
    assert "<TMP>" not in (golden / SELF_KEY / "gaps_empty.txt").read_text("utf-8")
    junit = (golden / SELF_KEY / "check_reports.junit.xml").read_text("utf-8")
    assert 'name="FIXTURE:REQ-1" classname="opencomplai.FIXTURE"' in junit
    sarif = json.loads(
        (golden / SELF_KEY / "check_reports.sarif.json").read_text("utf-8")
    )
    assert "FIXTURE:REQ-1" in {r["ruleId"] for r in sarif["runs"][0]["results"]}
    section = (golden / SELF_KEY / "report_section.html").read_text("utf-8")
    assert "<h2>Fixture framework</h2>" in section
    assert "<th>Evidence class</th>" in section
    assert "FIXTURE:REQ-1" in section
    summary = (golden / SELF_KEY / "check_reports.summary.md").read_text("utf-8")
    assert "| Requirement | Title | Status | Evidence |" in summary
    assert "| FIXTURE:REQ-1 |" in summary

    _run_all(fixtures, golden, runs / "b", monkeypatch, names, update=False)

    for case, golden_file in (
        ("gaps_evidenced", "gaps_evidenced.json"),
        ("check_reports", "check_reports.sarif.json"),
        ("check_reports", "check_reports.summary.md"),
        ("report_section", "report_section.html"),
    ):
        target = golden / SELF_KEY / golden_file
        original = target.read_bytes()
        data = bytearray(original)
        data[len(data) // 2] ^= 0x01
        target.write_bytes(bytes(data))
        with pytest.raises(AssertionError, match="drifted"):
            run_case(
                SELF_KEY,
                case,
                runs / f"c-{golden_file}",
                monkeypatch,
                fixtures=fixtures,
                golden=golden,
                update=False,
            )
        target.write_bytes(original)


def test_applicability_case(self_pack, monkeypatch):
    fixtures, golden, runs = self_pack
    app = fixtures / SELF_KEY / "applicability"
    app.mkdir()
    (app / "not_applicable.json").write_text(
        json.dumps(
            _self_manifest(
                framework_inputs={SELF_KEY: {"scope": {"trains_models": False}}}
            )
        ),
        encoding="utf-8",
    )
    assert _applicability(SELF_KEY, fixtures) == ["not_applicable"]
    # a shared scope key; the fixture pack has no applicability file, so no outcome
    run_case(
        SELF_KEY,
        "applicability_not_applicable",
        runs / "u",
        monkeypatch,
        fixtures=fixtures,
        golden=golden,
        update=True,
    )
    out = json.loads(
        (golden / SELF_KEY / "applicability_not_applicable.json").read_text("utf-8")
    )
    assert out["framework"] == SELF_KEY
    assert out["scope"] == {"trains_models": False}
    assert out["outcome"] is None
    run_case(
        SELF_KEY,
        "applicability_not_applicable",
        runs / "c",
        monkeypatch,
        fixtures=fixtures,
        golden=golden,
        update=False,
    )


def test_update_touches_only_its_own_directory(self_pack, monkeypatch):
    fixtures, golden, runs = self_pack
    other = golden / "OTHER"
    other.mkdir(parents=True)
    (other / "gaps_empty.json").write_text("keep\n", encoding="utf-8")
    keep = golden / SELF_KEY
    keep.mkdir()
    (keep / "later_card.html").write_text("later card\n", encoding="utf-8")
    _run_all(fixtures, golden, runs, monkeypatch, _self_names(), update=True)
    assert (other / "gaps_empty.json").read_text(encoding="utf-8") == "keep\n"
    assert (keep / "later_card.html").read_text(encoding="utf-8") == ("later card\n")


def test_missing_golden_names_the_update_command(self_pack, monkeypatch):
    fixtures, golden, runs = self_pack
    with pytest.raises(AssertionError, match=f"{UPDATE_ENV}={SELF_KEY}"):
        run_case(
            SELF_KEY,
            "gaps_empty",
            runs,
            monkeypatch,
            fixtures=fixtures,
            golden=golden,
            update=False,
        )


# --- layout failures --------------------------------------------------------


def test_discovered_pack_without_golden_directory_fails(tmp_path):
    fixtures, golden = _build_self_pack(tmp_path)
    problems = layout_problems(SELF_KEY, fixtures, golden, update=False)
    assert len(problems) == 1
    assert "no golden directory" in problems[0]
    assert f"{UPDATE_ENV}={SELF_KEY} uv run pytest" in problems[0]
    assert "-k FIXTURE" in problems[0]
    # update mode for that key is allowed to create the directory
    assert layout_problems(SELF_KEY, fixtures, golden, update=True) == []


def test_golden_directory_without_fixtures_fails(tmp_path):
    fixtures, golden = tmp_path / "fixtures", tmp_path / "golden"
    (golden / "ORPHAN").mkdir(parents=True)
    fixtures.mkdir()
    problems = layout_problems("ORPHAN", fixtures, golden, update=False)
    assert len(problems) == 1
    assert "has no fixtures" in problems[0]
    # a fixture directory without manifest.json is not a pack
    (fixtures / "ORPHAN" / "empty").mkdir(parents=True)
    assert discover(fixtures) == []
    assert layout_problems("ORPHAN", fixtures, golden, update=False)


def test_complete_layout_passes(tmp_path):
    fixtures, golden = _build_self_pack(tmp_path)
    (golden / SELF_KEY).mkdir(parents=True)
    assert layout_problems(SELF_KEY, fixtures, golden, update=False) == []


def test_no_packs_means_no_cases():
    if not discover():
        assert _cases() == []
    assert discover(Path("does-not-exist")) == []
