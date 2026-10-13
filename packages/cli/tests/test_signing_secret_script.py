"""Behaviour guards for scripts/signing-secret.sh, run against a stub ``gh``."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "signing-secret.sh"
_NAME = "OPENCOMPLAI_SIGNING_KEY"
_REPO = "acme/widgets"
_PRIV = "PRIVATE " + "KEY"
_PUB = "PUBLIC " + "KEY"
_PUB_BEGIN = "-----BEGIN " + _PUB + "-----"
_PRIV_MARK = "-----BEGIN " + _PRIV + "-----"

_STUB = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$STUB_OUT/argv.txt"
if [ "$1 $2" = "secret list" ]; then
  [ -n "${STUB_GH_SECRETS:-}" ] && printf '%s\\n' "$STUB_GH_SECRETS"
  exit 0
fi
if [ "$1 $2" = "secret set" ]; then
  cat > "$STUB_OUT/stdin.txt"
  exit "${STUB_GH_EXIT:-0}"
fi
exit 9
"""


def _bash() -> str:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available")
    return bash


@pytest.fixture
def env_dirs(tmp_path: Path) -> dict[str, Path]:
    pytest.importorskip("cryptography")
    if shutil.which("openssl") is None:
        pytest.skip("openssl not available")
    dirs = {}
    for name in ("bin", "cwd", "home", "tmp", "out", "empty"):
        d = tmp_path / name
        d.mkdir()
        dirs[name] = d
    gh = dirs["bin"] / "gh"
    gh.write_text(_STUB, encoding="utf-8", newline="\n")
    gh.chmod(0o755)
    return dirs


def _run(
    dirs: dict[str, Path],
    *args: str,
    trace: bool = False,
    path: str | None = None,
    extra: dict[str, str] | None = None,
    out: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = (
        path if path is not None else str(dirs["bin"]) + os.pathsep + env["PATH"]
    )
    env["HOME"] = str(dirs["home"])
    env["TMPDIR"] = env["TEMP"] = env["TMP"] = str(dirs["tmp"])
    env["STUB_OUT"] = str(out or dirs["out"])
    env.pop("SIGNING_KEY_PRIVATE", None)
    env.update(extra or {})
    cmd = [_bash(), *(["-x"] if trace else []), str(_SCRIPT), *args]
    return subprocess.run(
        cmd, env=env, cwd=dirs["cwd"], capture_output=True, text=True, check=False
    )


def _ok(dirs: dict[str, Path], **kw: object) -> subprocess.CompletedProcess[str]:
    proc = _run(dirs, _NAME, _REPO, **kw)  # type: ignore[arg-type]
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc


def _piped(out: Path) -> str:
    return (out / "stdin.txt").read_text(encoding="utf-8")


def _pem(b64: str) -> str:
    return base64.b64decode(b64, validate=True).decode("ascii")


def _files(dirs: dict[str, Path]) -> set[Path]:
    return {p for k in ("cwd", "home", "tmp") for p in dirs[k].rglob("*")}


def test_secret_goes_to_gh_on_stdin_only(env_dirs: dict[str, Path]) -> None:
    _ok(env_dirs)
    lines = (env_dirs["out"] / "argv.txt").read_text(encoding="utf-8").splitlines()
    assert lines[-1] == f"secret set {_NAME} --repo {_REPO}"
    for line in lines:
        for flag in ("--body", "-b ", "--body-file"):
            assert flag not in line
    assert _piped(env_dirs["out"]) != ""


def test_piped_value_is_accepted_by_resolve_key(
    env_dirs: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from opencomplai_core.signing import resolve_key

    _ok(env_dirs)
    value = _piped(env_dirs["out"])
    assert value == "".join(value.split())
    monkeypatch.setenv("SIGNING_KEY_PRIVATE", value)
    key = serialization.load_pem_private_key(resolve_key(), password=None)
    assert isinstance(key, Ed25519PrivateKey)


def test_private_key_never_in_output_or_files(env_dirs: dict[str, Path]) -> None:
    before = _files(env_dirs)
    for trace in (False, True):
        out = env_dirs["out"] / ("trace" if trace else "plain")
        out.mkdir()
        proc = _ok(env_dirs, trace=trace, out=out)
        b64 = _piped(out)
        pem = _pem(b64)
        body = [ln for ln in pem.splitlines() if ln and not ln.startswith("-----")]
        streams = proc.stdout + proc.stderr
        assert b64 not in streams
        assert pem.strip() not in streams
        assert _PRIV_MARK not in streams
        assert body
        for ln in body:
            assert ln not in streams
        for f in out.iterdir():
            if f.name != "stdin.txt":
                assert b64 not in f.read_text(encoding="utf-8")
    assert _files(env_dirs) == before


def test_public_key_is_printed_and_matches(env_dirs: dict[str, Path]) -> None:
    from cryptography.hazmat.primitives import serialization

    proc = _ok(env_dirs)
    key = serialization.load_pem_private_key(
        _pem(_piped(env_dirs["out"])).encode("ascii"), password=None
    )
    expected = (
        key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("ascii")
    )
    assert proc.stdout.count(_PUB_BEGIN) == 1
    assert expected in proc.stdout


def test_existing_secret_is_not_replaced_without_flag(
    env_dirs: dict[str, Path],
) -> None:
    extra = {"STUB_GH_SECRETS": f"OTHER\t2024\n{_NAME}\t2024"}
    proc = _run(env_dirs, _NAME, _REPO, extra=extra)
    assert proc.returncode == 3
    assert not (env_dirs["out"] / "stdin.txt").exists()
    assert _PUB_BEGIN not in proc.stdout
    proc = _run(env_dirs, _NAME, _REPO, "--replace", extra=extra)
    assert proc.returncode == 0, proc.stderr
    assert (env_dirs["out"] / "stdin.txt").exists()


def test_gh_failure_exits_nonzero_and_prints_no_public_key(
    env_dirs: dict[str, Path],
) -> None:
    proc = _run(env_dirs, _NAME, _REPO, extra={"STUB_GH_EXIT": "1"})
    assert proc.returncode != 0
    assert _PUB_BEGIN not in proc.stdout


@pytest.mark.parametrize(
    "args",
    [(), (_NAME,), ("lower_case", _REPO), (_NAME, "no-slash"), (_NAME, _REPO, "extra")],
)
def test_bad_arguments_exit_2(env_dirs: dict[str, Path], args: tuple[str, ...]) -> None:
    proc = _run(env_dirs, *args, path=str(env_dirs["empty"]))
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert not (env_dirs["out"] / "stdin.txt").exists()


def test_missing_gh_exits_2(env_dirs: dict[str, Path]) -> None:
    proc = _run(env_dirs, _NAME, _REPO, path=str(env_dirs["empty"]))
    assert proc.returncode == 2
    assert "gh" in proc.stderr


def test_script_parses_with_bash_n() -> None:
    proc = subprocess.run(
        [_bash(), "-n", str(_SCRIPT)], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0, proc.stderr
