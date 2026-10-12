"""`check -m a.json -m b.json`: per-system runs plus an unsigned summary."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from opencomplai_cli.commands.portfolio import safe_dir_name
from opencomplai_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()
PASS_PURPOSE = "customer support chatbot"
FAIL_PURPOSE = "employment screening and ranking"


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    for var in (
        "SIGNING_KEY_PRIVATE",
        "GITHUB_SHA",
        "CI_COMMIT_SHA",
        "OPENCOMPLAI_API_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(tmp_path / "state"))


def _init(path: Path, system_id: str, purpose: str = PASS_PURPOSE) -> Path:
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            system_id,
            "--intended-purpose",
            purpose,
            "--output",
            str(path),
        ],
    )
    assert result.exit_code == 0, result.output
    return path


def _summary(out: Path) -> dict:
    return json.loads((out / "portfolio-summary.json").read_text(encoding="utf-8"))


def test_two_manifests_write_per_system_dirs_and_summary(tmp_path):
    a = _init(tmp_path / "a.json", "alpha")
    b = _init(tmp_path / "b.json", "beta")
    result = runner.invoke(
        app, ["check", "-m", str(a), "-m", str(b), "--output-dir", "out"]
    )
    assert result.exit_code == 0, result.output
    out = tmp_path / "out"
    summary = _summary(out)
    assert [s["system_id"] for s in summary["systems"]] == ["alpha", "beta"]
    for entry in summary["systems"]:
        art = out / entry["system_id"] / "compliance-artifact.json"
        data = art.read_bytes()
        assert json.loads(data)["system_id"] == entry["system_id"]
        assert entry["artifact"] == f"{entry['system_id']}/compliance-artifact.json"
        assert entry["artifact_sha256"] == hashlib.sha256(data).hexdigest()
    assert not (tmp_path / "compliance-artifact.json").exists()
    assert not (tmp_path / "portfolio-summary.json").exists()


def test_worst_severity_exit_code_and_unsigned_summary(tmp_path):
    ok = _init(tmp_path / "ok.json", "ok-sys")
    bad = _init(tmp_path / "bad.json", "bad-sys", FAIL_PURPOSE)
    result = runner.invoke(
        app, ["check", "-m", str(ok), "-m", str(bad), "--output-dir", "out"]
    )
    assert result.exit_code == 1, result.output
    summary = _summary(tmp_path / "out")
    assert summary["signed"] is False
    assert summary["worst_exit_code"] == 1
    assert "signature" not in json.dumps(summary)
    codes = {s["system_id"]: s["exit_code"] for s in summary["systems"]}
    assert codes == {"ok-sys": 0, "bad-sys": 1}

    result = runner.invoke(
        app,
        ["check", "-m", str(ok), "-m", "gone.json", "--output-dir", "out2"],
    )
    assert result.exit_code == 2, result.output
    summary = _summary(tmp_path / "out2")
    assert summary["worst_exit_code"] == 2
    gone = next(s for s in summary["systems"] if s["system_id"] == "gone")
    assert gone["artifact"] is None
    assert gone["artifact_sha256"] is None
    assert gone["result"] == "validation_fail"


def test_glob_is_expanded_by_the_cli(tmp_path):
    _init(tmp_path / "sys-a.json", "ga")
    _init(tmp_path / "sys-b.json", "gb")
    result = runner.invoke(app, ["check", "-m", "sys-*.json", "--output-dir", "out"])
    assert result.exit_code == 0, result.output
    assert [s["system_id"] for s in _summary(tmp_path / "out")["systems"]] == [
        "ga",
        "gb",
    ]
    result = runner.invoke(app, ["check", "-m", "nope-*.json"])
    assert result.exit_code == 2
    assert not (tmp_path / "compliance-artifact.json").exists()


def test_multi_system_manifest_is_rejected(tmp_path):
    ok = _init(tmp_path / "ok.json", "ok-sys")
    for n, body in enumerate([{"system_id": "x", "systems": []}, [{"a": 1}]]):
        bad = tmp_path / f"bad{n}.json"
        bad.write_text(json.dumps(body), encoding="utf-8")
        single = runner.invoke(app, ["check", "-m", str(bad), "--output-dir", "o1"])
        multi = runner.invoke(
            app, ["check", "-m", str(ok), "-m", str(bad), "--output-dir", "o2"]
        )
        assert single.exit_code == 2
        assert multi.exit_code == 2
        assert not (tmp_path / "o1").exists()
        assert not (tmp_path / "o2").exists()
        assert not (tmp_path / "compliance-artifact.json").exists()


def test_duplicate_system_id_exits_2_before_running(tmp_path):
    a = _init(tmp_path / "a.json", "same")
    b = _init(tmp_path / "b.json", "same")
    result = runner.invoke(
        app, ["check", "-m", str(a), "-m", str(b), "--output-dir", "out"]
    )
    assert result.exit_code == 2
    assert not (tmp_path / "out").exists()


def _normalise(text: str) -> str:
    text = re.sub(r"\d{4}-\d{2}-\d{2}T[\d:.]+(?:Z|[+-]\d{2}:\d{2})?", "<TS>", text)
    # the human summary prints duration_ms unquoted (duration_ms:  14); the JSON artifact quotes the key
    return re.sub(
        r'("?(?:duration_ms|install_id)"?:\s*)("[^"]*"|[0-9.]+)', r"\1<X>", text
    )


def test_single_manifest_default_unchanged(tmp_path):
    _init(tmp_path / "system-manifest.json", "solo")
    default = runner.invoke(app, ["check"])
    first = (tmp_path / "compliance-artifact.json").read_text(encoding="utf-8")
    (tmp_path / "compliance-artifact.json").unlink()
    explicit = runner.invoke(app, ["check", "-m", "system-manifest.json"])
    second = (tmp_path / "compliance-artifact.json").read_text(encoding="utf-8")
    assert default.exit_code == explicit.exit_code == 0
    assert _normalise(default.stdout) == _normalise(explicit.stdout)
    assert _normalise(first) == _normalise(second)
    assert not (tmp_path / "portfolio-summary.json").exists()


def test_safe_dir_name():
    assert safe_dir_name("../x") == ".._x"
    assert safe_dir_name("a/b") == "a_b"
    assert safe_dir_name("..") == "_"
    assert safe_dir_name("") == "_"
    assert safe_dir_name("ok-1.2_x") == "ok-1.2_x"


def test_portfolio_accepts_file_path_options(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a = _init(tmp_path / "a.json", "alpha")
    b = _init(tmp_path / "b.json", "beta")
    log = tmp_path / "oversight.json"
    log.write_text("[]")
    result = runner.invoke(
        app,
        [
            "check", "-m", str(a), "-m", str(b),
            "--repo-root", ".",
            "--oversight-log", str(log),
            "--report-junit", "r.xml",
            "--sarif-output", "r.sarif",
            "--summary-md", "r.md",
            "--output-dir", "out",
        ],
    )  # fmt: skip
    assert result.exception is None, result.output
    assert result.exit_code == 0, result.output
    out = tmp_path / "out"
    assert (out / "alpha" / "compliance-artifact.json").is_file()
    assert (out / "beta" / "compliance-artifact.json").is_file()
    assert (out / "portfolio-summary.json").is_file()


def _alpha_set(tmp_path: Path) -> Path:
    sample = tmp_path / "set.json"
    sample.write_text(
        json.dumps({"eval_set_id": "s1", "system_id": "alpha", "prompts": ["hello"]}),
        encoding="utf-8",
    )
    return sample


def _two_systems(tmp_path: Path) -> tuple[Path, Path]:
    return _init(tmp_path / "a.json", "alpha"), _init(tmp_path / "b.json", "beta")


def test_portfolio_sample_set_is_converted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a, b = _two_systems(tmp_path)
    sample = _alpha_set(tmp_path)
    result = runner.invoke(
        app,
        ["check", "-m", str(a), "-m", str(b), "--sample-set", str(sample),
         "--output-dir", "out"],
    )  # fmt: skip
    assert "must match manifest system_id" not in result.output
    assert "AttributeError" not in result.output
    out = tmp_path / "out"
    for sid in ("alpha", "beta"):
        report = json.loads(
            (out / sid / "eval-report.json").read_text(encoding="utf-8")
        )
        assert report["system_id"] == sid
    copy = json.loads((out / "beta" / "sample-set.json").read_text(encoding="utf-8"))
    assert copy["system_id"] == "beta"
    assert all(e["exit_code"] != 2 for e in _summary(out)["systems"])


def test_portfolio_sample_set_original_untouched(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a, b = _two_systems(tmp_path)
    sample = _alpha_set(tmp_path)
    before = sample.read_bytes()
    runner.invoke(
        app,
        ["check", "-m", str(a), "-m", str(b), "--sample-set", str(sample),
         "--output-dir", "out"],
    )  # fmt: skip
    assert sample.read_bytes() == before


def test_single_manifest_sample_set_mismatch_still_exits_2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    b = _init(tmp_path / "b.json", "beta")
    sample = _alpha_set(tmp_path)
    result = runner.invoke(
        app, ["check", "-m", str(b), "--sample-set", str(sample), "--output-dir", "out"]
    )
    assert result.exit_code == 2
    assert "must match manifest system_id 'beta'" in result.output


def test_portfolio_sample_set_invalid_passes_through(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a, b = _two_systems(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    cases = (
        ("out", bad, "not valid JSON"),
        ("out2", tmp_path / "gone.json", "sample set not found"),
    )
    for out_name, path, message in cases:
        result = runner.invoke(
            app,
            ["check", "-m", str(a), "-m", str(b), "--sample-set", str(path),
             "--output-dir", out_name],
        )  # fmt: skip
        assert message in result.output
        out = tmp_path / out_name
        systems = _summary(out)["systems"]
        assert [e["exit_code"] for e in systems] == [2, 2]
        assert not list(out.rglob("sample-set.json"))


def test_portfolio_docs_describe_shared_sample_set():
    docs = Path(__file__).resolve().parents[3] / "docs" / "src" / "cli"
    check = (docs / "check.md").read_text(encoding="utf-8")
    portfolio = (docs / "portfolio.md").read_text(encoding="utf-8")
    assert "sample-set.json" in check
    assert "sample-set.json" in portfolio
    assert "must match the manifest. |" not in check
    assert "With several manifests the CLI rewrites `system_id`" in check


def test_coerce_path_params_converts_strings():
    from opencomplai_cli.commands.portfolio import coerce_path_params
    from typer.main import get_command

    cmd = get_command(app).commands["check"]
    got = coerce_path_params(
        {"repo_root": ".", "commit_ref": "abc", "scan_baseline": None}, cmd
    )
    assert got["repo_root"] == Path(".")
    assert isinstance(got["repo_root"], Path)
    assert got["commit_ref"] == "abc"
    assert got["scan_baseline"] is None


def test_portfolio_writes_one_report_per_system(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a = _init(tmp_path / "a.json", "alpha")
    b = _init(tmp_path / "b.json", "beta", FAIL_PURPOSE)
    result = runner.invoke(
        app,
        ["check", "-m", str(a), "-m", str(b),
         "--report-junit", "r.xml", "--sarif-output", "r.sarif",
         "--summary-md", "r.md", "--output-dir", "out"],
    )  # fmt: skip
    assert result.exit_code == 1, result.output
    for bare in ("r.xml", "r.sarif", "r.md"):
        assert not (tmp_path / bare).exists()
    for sid in ("alpha", "beta"):
        for ext in ("xml", "sarif", "md"):
            assert (tmp_path / f"r.{sid}.{ext}").is_file()
    for sid in ("alpha", "beta"):
        sarif = json.loads((tmp_path / f"r.{sid}.sarif").read_text(encoding="utf-8"))
        assert sarif["runs"][0]["properties"]["system_id"] == sid
        other = "beta" if sid == "alpha" else "alpha"
        md = (tmp_path / f"r.{sid}.md").read_text(encoding="utf-8")
        assert sid in md
        assert other not in md
    assert "<failure" not in (tmp_path / "r.alpha.xml").read_text(encoding="utf-8")
    assert "<failure" in (tmp_path / "r.beta.xml").read_text(encoding="utf-8")


def test_single_manifest_report_paths_unchanged(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a = _init(tmp_path / "a.json", "solo")
    result = runner.invoke(
        app,
        ["check", "-m", str(a), "--report-junit", "r.xml",
         "--sarif-output", "r.sarif", "--summary-md", "r.md",
         "--output-dir", "out"],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    for bare in ("r.xml", "r.sarif", "r.md"):
        assert (tmp_path / bare).is_file()
    assert not list(tmp_path.glob("r.solo.*"))


def test_portfolio_report_docs_describe_per_system_names():
    root = Path(__file__).resolve().parents[3]
    check = (root / "docs/src/cli/check.md").read_text(encoding="utf-8")
    guide = (root / "docs/src/guides/ci-integration.md").read_text(encoding="utf-8")
    assert "every system writes the same path" not in guide
    assert "<stem>.<system_id><ext>" in check
    assert "<stem>.<system_id><ext>" in guide
