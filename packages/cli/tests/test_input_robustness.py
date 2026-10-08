"""CLI input and JSON-mode robustness (SU-107a): the scan-report reader, pure
JSON stdout, typed opencomplai.yaml, unknown manifest keys, and `check`
validating every input before it writes or halts anything."""

from __future__ import annotations

import codecs
import json
import locale
from pathlib import Path

import pytest
from opencomplai_cli.inputs import read_json_file
from opencomplai_cli.main import FailOnLevel, app
from opencomplai_core.models import SystemState
from opencomplai_core.project_config import FAIL_ON_LEVELS
from opencomplai_core.system_state_store import load_state
from typer.testing import CliRunner

runner = CliRunner()


def _isolate(tmp_path: Path, monkeypatch) -> Path:
    """Chdir to tmp_path, no service, and a private HALT-WIRE state dir."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENCOMPLAI_API_URL", raising=False)
    state_dir = tmp_path / "state"
    monkeypatch.setenv("OPENCOMPLAI_STATE_DIR", str(state_dir))
    return state_dir


def _init(tmp_path: Path, system_id: str = "robust-sys") -> Path:
    manifest = tmp_path / "system-manifest.json"
    result = runner.invoke(
        app,
        [
            "init",
            "--system-id",
            system_id,
            "--intended-purpose",
            "customer support chatbot",
            "--output",
            str(manifest),
        ],
    )
    assert result.exit_code == 0, result.output
    return manifest


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "requirements.txt").write_text("face_recognition\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "face.py").write_text(
        "import face_recognition\n", encoding="utf-8"
    )
    return tmp_path


def _utf8(text: str) -> bytes:
    return text.encode("utf-8")


def _utf8_bom(text: str) -> bytes:
    return codecs.BOM_UTF8 + text.encode("utf-8")


def _utf16_le_bom(text: str) -> bytes:
    return codecs.BOM_UTF16_LE + text.encode("utf-16-le")


def _bare(text: str) -> bytes:
    return json.dumps(json.loads(text)["payload"]).encode("utf-8")


# --- read_json_file ---------------------------------------------------------


def test_read_json_file_decodes_and_unwraps(tmp_path, monkeypatch):
    monkeypatch.setattr(locale, "getpreferredencoding", lambda _=True: "cp1252")
    envelope = {"tool_version": "1", "payload": {"k": "v"}}
    text = json.dumps(envelope, ensure_ascii=False)
    f = tmp_path / "f.json"
    for encode in (_utf8, _utf8_bom, _utf16_le_bom):
        f.write_bytes(encode(text))
        assert read_json_file(f) == {"k": "v"}
    f.write_bytes(json.dumps({"k": "—"}, ensure_ascii=False).encode("cp1252"))
    assert read_json_file(f) == {"k": "—"}
    f.write_bytes(b'{"k": 1}')  # bare, no envelope keys: returned as is
    assert read_json_file(f) == {"k": 1}
    f.write_bytes(b'{"payload": 1}')  # `payload` alone is not an envelope
    assert read_json_file(f) == {"payload": 1}
    for bad in (b"", b"   ", b"{nope"):
        f.write_bytes(bad)
        with pytest.raises(ValueError, match="not valid JSON"):
            read_json_file(f)


# --- scan-report input ------------------------------------------------------


@pytest.mark.parametrize(
    "encode",
    [_utf8, _utf8_bom, _utf16_le_bom, _bare],
    ids=["utf8", "utf8-bom", "utf16-bom", "bare"],
)
def test_scan_report_accepts_scan_json_output(tmp_path, monkeypatch, encode):
    _isolate(tmp_path, monkeypatch)
    manifest = _init(tmp_path)
    repo = _repo(tmp_path)
    scan = runner.invoke(
        app,
        [
            "scan",
            "--manifest",
            str(manifest),
            "--repo-root",
            str(repo),
            "-o",
            "json",
            "--no-emit-evidence",
        ],
    )
    assert scan.exit_code == 0, scan.output
    scan_file = tmp_path / "scan.json"
    scan_file.write_bytes(encode(scan.stdout))

    gaps = runner.invoke(app, ["gaps", "--scan-report", str(scan_file), "-o", "json"])
    assert gaps.exit_code == 0, gaps.output
    json.loads(gaps.stdout)
    # `recommend` has the second --scan-report reader (`report` takes none)
    rec = runner.invoke(
        app,
        [
            "recommend",
            "--scan-report",
            str(scan_file),
            "--output",
            str(tmp_path / "fx"),
        ],
    )
    assert rec.exit_code == 0, rec.output


@pytest.mark.parametrize("cmd", ["gaps", "recommend"])
@pytest.mark.parametrize("content", [b"", b"{nope", b'{"x": 1}'])
def test_scan_report_bad_file_exits_2(tmp_path, monkeypatch, cmd, content):
    _isolate(tmp_path, monkeypatch)
    _init(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_bytes(content)
    result = runner.invoke(app, [cmd, "--scan-report", str(bad)])
    assert result.exit_code == 2, result.output
    assert "scan report" in result.output
    assert isinstance(result.exception, SystemExit)  # no traceback


# --- JSON-mode stdout purity ------------------------------------------------


def test_json_mode_stdout_is_pure_json(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    manifest = _init(tmp_path)
    repo = _repo(tmp_path)
    (tmp_path / "opencomplai.yaml").write_text(
        "scan:\n  fail_on: none\n", encoding="utf-8"
    )
    assert not (tmp_path / ".ocignore").exists()
    base = ["--manifest", str(manifest)]
    for args in (
        ["scan", *base, "--repo-root", str(repo), "-o", "json", "--no-emit-evidence"],
        ["gaps", *base, "-o", "json"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
        json.loads(result.stdout)
    # the scan created .ocignore; remove it so `check --scan` bootstraps it again
    (tmp_path / ".ocignore").unlink()
    result = runner.invoke(
        app,
        [
            "check",
            *base,
            "--scan",
            "--repo-root",
            str(repo),
            "--no-emit-evidence",
            "-o",
            "json",
        ],
    )
    assert result.exit_code in (0, 1), result.output
    json.loads(result.stdout)


# --- opencomplai.yaml types -------------------------------------------------


def test_fail_on_levels_match_cli_enum():
    assert set(FAIL_ON_LEVELS) == {level.value for level in FailOnLevel}


def test_bad_project_config_type_exits_2(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    manifest = _init(tmp_path)
    (tmp_path / "opencomplai.yaml").write_text(
        "scan:\n  fail_on: loud\n", encoding="utf-8"
    )
    result = runner.invoke(
        app, ["scan", "--manifest", str(manifest), "--repo-root", str(tmp_path)]
    )
    assert result.exit_code == 2, result.output
    assert "scan.fail_on" in result.output
    assert isinstance(result.exception, SystemExit)  # no traceback


# --- unknown manifest keys --------------------------------------------------


def test_unknown_manifest_key_warns_and_strict_exits_2(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    manifest = _init(tmp_path)
    data = json.loads(manifest.read_text())
    data["intended_purpse"] = "typo"
    manifest.write_text(json.dumps(data))

    result = runner.invoke(app, ["gaps", "--manifest", str(manifest), "-o", "json"])
    assert result.exit_code == 0, result.output
    assert "unknown manifest key(s): intended_purpse" in result.stderr
    json.loads(result.stdout)

    strict = runner.invoke(
        app, ["gaps", "--manifest", str(manifest), "-o", "json", "--strict"]
    )
    assert strict.exit_code == 2
    assert "intended_purpse" in strict.stderr
    assert strict.stdout == ""

    for args in (
        ["scan", "--repo-root", str(tmp_path), "--strict"],
        ["check", "--strict"],
    ):
        result = runner.invoke(app, [args[0], "--manifest", str(manifest), *args[1:]])
        assert result.exit_code == 2, (args, result.output)
        assert "intended_purpse" in result.stderr


# --- check validates before it emits ----------------------------------------


def _assert_nothing_written(tmp_path: Path, state_dir: Path, system_id: str) -> None:
    assert load_state(state_dir, system_id) == SystemState.RUNNING
    assert not state_dir.exists() or not any(state_dir.iterdir())
    for name in ("compliance-artifact.json", "scan-report.json", "eval-report.json"):
        assert not (tmp_path / name).exists(), name


def test_check_bad_input_exits_2_without_halt_record(tmp_path, monkeypatch):
    state_dir = _isolate(tmp_path, monkeypatch)
    manifest = _init(tmp_path, "bad-input-sys")
    data = json.loads(manifest.read_text())
    data["compliance_targets"] = ["EU_AI_ACT", "NIST_AI_RMF"]
    data["framework_inputs"] = {
        "NIST_AI_RMF": {"excluded": {"NOPE:REQ": "does not exist"}}
    }
    manifest.write_text(json.dumps(data))

    # a recognised change context trips the Art. 25 trap (exit 4) on valid input
    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest),
            "--with-gaps",
            "--change-context",
            "model_retrain",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "NOPE:REQ" in result.stderr
    _assert_nothing_written(tmp_path, state_dir, "bad-input-sys")


@pytest.mark.parametrize("content", [b"{nope", None], ids=["malformed", "missing"])
def test_check_bad_baseline_exits_2_without_halt_record(tmp_path, monkeypatch, content):
    state_dir = _isolate(tmp_path, monkeypatch)
    manifest = _init(tmp_path, "bad-baseline-sys")
    baseline = tmp_path / "baseline.json"
    if content is not None:
        baseline.write_bytes(content)
    result = runner.invoke(
        app,
        [
            "check",
            "--manifest",
            str(manifest),
            "--baseline",
            str(baseline),
            "--change-context",
            "model_retrain",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "baseline" in result.stderr
    _assert_nothing_written(tmp_path, state_dir, "bad-baseline-sys")
