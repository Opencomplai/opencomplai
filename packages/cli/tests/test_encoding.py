"""Tests for the ASCII fallback that keeps the CLI alive on legacy code pages.

The regression these guard is not cosmetic: before ``_encoding``, running
``opencomplai --help`` with ``sys.stdout`` on cp437 - the default OEM code
page of a Windows console - raised ``UnicodeEncodeError`` part-way through
rendering the banner and exited 1.
"""

import io
import json
import os
import subprocess
import sys

import pytest
from opencomplai_cli._encoding import (
    ASCII_FALLBACKS,
    ERROR_HANDLER_NAME,
    encoding_is_lossy,
    install_ascii_fallback,
)
from opencomplai_core.models import (
    HumanOversight,
    OversightRole,
    SystemManifest,
    SystemState,
)
from opencomplai_core.signing import generate_keypair
from opencomplai_core.system_state_store import save_state

BANNER = "Opencomplai — Open-source AI compliance for a trustworthy future."


def _lossy_stream(encoding: str = "cp437") -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(), encoding=encoding, newline="")


def test_handler_transliterates_the_characters_the_cli_emits():
    install_ascii_fallback()  # registers the handler without touching streams
    text = "em—dash arrow→here section§ref"
    assert text.encode("cp437", errors=ERROR_HANDLER_NAME) == (
        b"em-dash arrow->here sectionSref"
    )


def test_handler_falls_back_to_question_mark_for_unknown_characters():
    install_ascii_fallback()
    # Not in the table, and not representable in cp437: must degrade rather
    # than raise, matching what a lossy terminal did before this module.
    assert "漢字".encode("cp437", errors=ERROR_HANDLER_NAME) == b"??"


def test_handler_refuses_to_touch_decode_errors():
    """Silently mangling *input* would be a much worse bug than mangling output."""
    install_ascii_fallback()
    with pytest.raises(UnicodeDecodeError):
        b"\xff\xfe".decode("utf-8", errors=ERROR_HANDLER_NAME)


@pytest.mark.parametrize(
    ("encoding", "expected"),
    [
        ("utf-8", False),
        ("utf-16", False),
        ("cp437", True),
        ("cp1252", True),  # has the em dash, but not the arrows
        ("ascii", True),
        ("not-a-real-codec", True),
        (None, False),
    ],
)
def test_encoding_is_lossy(encoding, expected):
    assert encoding_is_lossy(encoding) is expected


def test_install_leaves_utf8_streams_alone():
    stream = _lossy_stream("utf-8")
    assert install_ascii_fallback(stream) == []
    stream.write(BANNER)
    stream.flush()
    # The real glyph survives - this is the common case and must not regress.
    assert "—".encode() in stream.buffer.getvalue()


def test_install_reconfigures_a_lossy_stream():
    stream = _lossy_stream("cp437")
    assert install_ascii_fallback(stream) == [stream]
    stream.write(BANNER)
    stream.flush()
    assert b"Opencomplai - Open-source" in stream.buffer.getvalue()


def test_install_without_the_fix_would_raise():
    """Control: the same write on an untouched cp437 stream still blows up,
    proving the test above is exercising the fallback and not some ambient
    tolerance of the encoding."""
    stream = _lossy_stream("cp437")
    with pytest.raises(UnicodeEncodeError):
        stream.write(BANNER)


def test_install_is_idempotent():
    stream = _lossy_stream("cp437")
    assert install_ascii_fallback(stream) == [stream]
    assert install_ascii_fallback(stream) == []


def test_install_ignores_streams_that_cannot_be_reconfigured():
    assert install_ascii_fallback(io.StringIO()) == []


def test_every_fallback_is_pure_ascii():
    for source, replacement in ASCII_FALLBACKS.items():
        assert replacement.isascii(), f"{source!r} maps to non-ASCII {replacement!r}"


def test_help_survives_a_legacy_codepage():
    """End-to-end: the actual failure from the bug report."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp437"
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    env["COLUMNS"] = "80"

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; sys.argv = ['opencomplai', '--help']\n"
            "from opencomplai_cli.main import app\n"
            "app()\n",
        ],
        capture_output=True,
        env=env,
    )

    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    assert b"Opencomplai - Open-source AI compliance" in proc.stdout


_PROBE = "import locale;print(locale.getpreferredencoding(False))"
_RUN = (
    "import sys; sys.argv[0]='opencomplai'; from opencomplai_cli.main import app; app()"
)


def _run_non_utf8(args, cwd, env_extra=None, code=_RUN):
    """Run the CLI with UTF-8 mode off and a non-UTF-8 locale (the Windows default)."""
    env = dict(os.environ)
    env.pop("PYTHONUTF8", None)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    env["PYTHONIOENCODING"] = "utf-8"
    env["LC_ALL"] = "C"
    env["PYTHONCOERCECLOCALE"] = "0"
    env["HOME"] = env["USERPROFILE"] = str(cwd)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, "-X", "utf8=0", "-c", code, *args],
        capture_output=True,
        cwd=cwd,
        env=env,
    )


@pytest.fixture(scope="module")
def _non_utf8_locale(tmp_path_factory):
    out = _run_non_utf8([], tmp_path_factory.mktemp("probe"), code=_PROBE)
    enc = out.stdout.decode("ascii", errors="replace").strip().lower().replace("_", "-")
    if enc in {"utf-8", "utf8"}:
        pytest.skip("locale default is UTF-8; the test would pass vacuously")


# argv must stay ASCII: an ASCII locale decodes non-ASCII arguments with
# surrogate escapes on POSIX; the non-ASCII text goes through the manifest file.
@pytest.mark.usefixtures("_non_utf8_locale")
def test_qms_generate_non_ascii_without_utf8_mode(tmp_path):
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps(
            {
                "system_id": "Sys-Lodz",
                "intended_purpose": "Überwachung der Qualität",
                # rendered into the QMS document (clause h), so the output proves the read
                "monitoring_approach": "Überwachung der Qualität",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out.md"
    proc = _run_non_utf8(
        [
            "qms",
            "generate",
            "--manifest",
            str(manifest),
            "--system-id",
            "Sys-Lodz",
            "--repo-root",
            str(tmp_path),
            "--output",
            str(out),
            "--scan-report",
            str(tmp_path / "missing-scan.json"),
            "--eval-report",
            str(tmp_path / "missing-eval.json"),
        ],
        tmp_path,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    assert "Überwachung" in out.read_bytes().decode("utf-8")


# argv must stay ASCII: an ASCII locale decodes non-ASCII arguments with
# surrogate escapes on POSIX; the non-ASCII text goes through the manifest file.
@pytest.mark.usefixtures("_non_utf8_locale")
def test_oversight_log_non_ascii_without_utf8_mode(tmp_path):
    generate_keypair(tmp_path / "keys")
    state = tmp_path / "state"
    save_state(
        state,
        "ov-sys",
        SystemState.HALTED_PENDING_REVIEW,
        reason="trap_detected",
        commit_ref="abc",
    )
    manifest = SystemManifest(
        system_id="ov-sys",
        intended_purpose="Überwachung der Qualität",
        human_oversight=HumanOversight(roles=[OversightRole(role="Aufsicht")]),
    )
    mpath = tmp_path / "m.json"
    mpath.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )
    proc = _run_non_utf8(
        [
            "approve",
            "--system-id",
            "ov-sys",
            "--approver",
            "qa@example.com",
            "--key",
            str(tmp_path / "keys" / "signing.key"),
            "--role",
            "Aufsicht",
            "--manifest",
            str(mpath),
            "--output",
            "json",
        ],
        tmp_path,
        {"OPENCOMPLAI_STATE_DIR": str(state)},
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    log = (state / "oversight-log.json").read_bytes().decode("utf-8")
    entry = json.loads(log.splitlines()[-1])
    assert entry["payload"]["role"] == "Aufsicht"
