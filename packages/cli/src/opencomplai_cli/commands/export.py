"""`opencomplai export` -- write one neutral evidence package from an artifact.

Moves data, never gates: exit 0 whatever the verdict inside. Reads only the
artifact path it is given (and, with `--sign`, the signing key); writes only
`--out` and `--artifact-out`. Nothing is sent anywhere. `err_console` comes
lazily from `opencomplai_cli.main` (a module-level import back into main would
be circular).

The input is the artifact `check` wrote; `--with-gaps` is not needed. An
artifact without a gap report exports with `gaps_included` false and no articles.

The package is signed only with `--sign`, under its own signing domain; without
it the bytes are exactly as before. The `evidence-package` kind of
`opencomplai verify` is registered at the bottom of this module.
"""

from __future__ import annotations

import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

import typer
from opencomplai_core.evidence_package import (
    EvidencePackage,
    build_evidence_package,
    package_to_csv,
    package_to_json,
    sign_package,
    verify_package,
)
from opencomplai_core.signing import SigningKeyError
from rich.markup import escape

from opencomplai_cli.check_signing import signing_key_available
from opencomplai_cli.commands.verify import (
    VerifyInputError,
    VerifyResult,
    register_kind,
)
from opencomplai_cli.inputs import read_json_file


class ExportFormat(StrEnum):
    json = "json"
    csv = "csv"


def _fail(message: str) -> NoReturn:
    from opencomplai_cli import main as _main

    _main.err_console.print(f"[red]Error:[/red] {escape(message)}")
    sys.exit(2)


def export_cmd(
    artifact: Path = typer.Argument(
        ..., help="Path to a compliance-artifact.json written by `check`"
    ),
    fmt: ExportFormat = typer.Option(
        ExportFormat.json,
        "--format",
        help="json (the package) or csv (one row per article)",
    ),
    out: Path | None = typer.Option(
        None, "--out", help="Write the package to this file instead of stdout"
    ),
    artifact_out: Path | None = typer.Option(
        None,
        "--artifact-out",
        help="Also write the embedded artifact, ready for `opencomplai verify`",
    ),
    sign: bool = typer.Option(
        False,
        "--sign",
        help="Sign the whole JSON package (not valid with --format csv)",
    ),
    key: Path | None = typer.Option(
        None, "--key", help="Private key PEM; SIGNING_KEY_PRIVATE takes precedence"
    ),
) -> None:
    """Export one neutral, schema-validated evidence package (JSON or CSV)."""
    from opencomplai_cli import main as _main

    try:
        raw = read_json_file(artifact)
        pkg = build_evidence_package(raw)
    except (OSError, ValueError) as e:
        _fail(str(e))

    # Everything that can refuse happens before any file is written.
    if sign:
        if fmt == ExportFormat.csv:
            _fail("--sign signs the JSON package; the CSV carries no signature")
        # Resolved here: main imports this module before it defines _SIGNING_KEY.
        key_path = key or _main._SIGNING_KEY
        if not signing_key_available(key_path):
            _fail(
                "--sign needs a signing key. Run `opencomplai init` or set "
                "SIGNING_KEY_PRIVATE (base64 PEM), or drop --sign for an "
                "unsigned package."
            )
        try:
            pkg = sign_package(pkg, key_path)
        except (SigningKeyError, ValueError) as e:
            _fail(f"signing failed: {e}")

    text = package_to_csv(pkg) if fmt == ExportFormat.csv else package_to_json(pkg)
    try:
        if artifact_out is not None:
            # Same bytes semantics the signature covers: parses to the same model.
            artifact_out.write_text(
                json.dumps(pkg.artifact, indent=2) + "\n",
                encoding="utf-8",
                newline="",
            )
        if out is not None:
            out.write_text(text, encoding="utf-8", newline="")
    except OSError as e:
        _fail(str(e))
    if out is None:
        typer.echo(text, nl=False)


def verify_evidence_package(path: Path, pub_key: Path | None) -> VerifyResult:
    try:
        raw = json.loads(path.read_bytes())
    except OSError as exc:
        raise VerifyInputError(f"cannot read {path}: {exc.strerror or exc}") from None
    except ValueError:
        raise VerifyInputError(f"{path} is not valid JSON") from None
    try:
        if not isinstance(raw, dict):
            raise ValueError("not an object")
        EvidencePackage.model_validate(raw)
    except ValueError:  # pydantic ValidationError is a ValueError
        raise VerifyInputError(f"{path} is not a valid evidence package") from None

    # Must come first: a failed verify cannot tell unsigned from tampered.
    if raw.get("package_signature") is None:
        return VerifyResult(
            "evidence-package", "unsigned", "no package signature present"
        )

    from opencomplai_cli import main as _main

    key = pub_key or _main._SIGNING_PUB
    if not key.is_file():
        raise VerifyInputError(f"public key file not found: {key}")
    # The RAW dict, never a re-dumped model: the signed values are the file's.
    status, detail = verify_package(raw, key)
    return VerifyResult("evidence-package", status, detail)


register_kind("evidence-package", verify_evidence_package)
