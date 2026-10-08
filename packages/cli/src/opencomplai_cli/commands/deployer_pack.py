"""`opencomplai deployer-pack build` and the `deployer-pack` verify kind.

Seals the Art. 13(3) instructions-for-use JSON (written by `opencomplai
instructions generate`) into one portable pack named after its own SHA-256. The
pack is generated offline and never uploaded; only its hash and counts reach the
artifact `summaries.packs` (see `opencomplai_core.deployer_pack`).

`console`/`err_console` and the key paths are obtained lazily from
`opencomplai_cli.main` (it imports this module to register the sub-typer, so a
top-level import is circular). Importing this module also registers the
`deployer-pack` kind with `opencomplai verify`.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from enum import StrEnum
from pathlib import Path

import typer
from opencomplai_core import deployer_pack as core
from opencomplai_core.instructions_for_use import IFUDocument
from opencomplai_core.signing import SigningKeyError

from opencomplai_cli.commands.verify import (
    VerifyInputError,
    VerifyResult,
    register_kind,
)

app = typer.Typer(help="Signed deployer pack (Art. 13) commands.")


class OutputFormat(StrEnum):
    human = "human"
    json = "json"


def _today() -> str:
    """The only clock read for the pack; tests patch it (E-14)."""
    return date.today().isoformat()


def _fail(message: str) -> None:
    from opencomplai_cli import main as _main

    _main.err_console.print(f"[red]Error:[/red] {message}", soft_wrap=True)
    sys.exit(2)


@app.command("build")
def build_cmd(
    instructions: Path = typer.Option(
        ...,
        "--instructions",
        help="instructions_for_use.json written by `opencomplai instructions generate`",
    ),
    system_id: str | None = typer.Option(
        None, "--system-id", help="Defaults to the system_id in the instructions file"
    ),
    output_dir: Path = typer.Option(Path("./deployer-pack"), "--output-dir"),
    sign: bool = typer.Option(
        False,
        "--sign/--no-sign",
        help="Sign with the signing key; exits 2 before writing when none is available",
    ),
    issued_on: str | None = typer.Option(
        None, "--issued-on", help="YYYY-MM-DD; defaults to today"
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Seal an instructions-for-use document into a hash-named deployer pack.

    The same inputs and day give byte-identical output. Packs are never uploaded.
    """
    from opencomplai_cli import main as _main
    from opencomplai_cli.check_signing import signing_key_available
    from opencomplai_cli.publish import _cli_version

    try:
        content = json.loads(instructions.read_text(encoding="utf-8"))
        IFUDocument.model_validate(content)
    except (OSError, ValueError) as exc:  # pydantic ValidationError is a ValueError
        _fail(
            f"{instructions} is not an instructions-for-use document "
            f"(`opencomplai instructions generate` output): {exc}"
        )
    sid = system_id or content.get("system_id")
    if not isinstance(sid, str) or not sid:
        _fail("--system-id is required: the instructions file carries no system_id")
    day = issued_on or _today()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        _fail(f"--issued-on must be YYYY-MM-DD, got '{day}'")
    # Before anything is built or written.
    if sign and not signing_key_available(_main._SIGNING_KEY):
        _fail(
            "--sign needs a signing key. Run `opencomplai init` or set "
            "SIGNING_KEY_PRIVATE (base64 PEM), or drop --sign for an unsigned pack."
        )
    try:
        pack = core.build_pack(
            content,
            system_id=sid,
            issued_on=day,
            generator_version=_cli_version(),
            private_key_path=_main._SIGNING_KEY if sign else None,
        )
    except SigningKeyError as exc:
        _fail(f"signing failed: {exc}")

    digest = pack.integrity.pack_sha256
    path = output_dir / f"deployer_pack_{digest[:12]}.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(pack.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    path.write_bytes(text.encode("utf-8"))

    c = pack.completeness
    if output == OutputFormat.json:
        print(
            json.dumps(
                {
                    "pack_sha256": digest,
                    "path": str(path),
                    "signed": pack.integrity.signature is not None,
                    "items_provided": c.items_provided,
                    "items_not_captured": c.items_not_captured,
                }
            )
        )
        return
    _main.console.print(f"[bold]Deployer pack written[/bold] {path}", soft_wrap=True)
    _main.console.print(f"  pack_sha256: {digest}", soft_wrap=True)
    _main.console.print(
        f"  {'signed' if pack.integrity.signature else 'unsigned'}; "
        f"{c.items_provided} of {c.items_total} items provided",
        soft_wrap=True,
    )


def verify_deployer_pack(path: Path, pub_key: Path | None) -> VerifyResult:
    import jsonschema

    try:
        raw = json.loads(path.read_bytes())
    except OSError as exc:
        raise VerifyInputError(f"cannot read {path}: {exc.strerror or exc}") from None
    except ValueError:
        raise VerifyInputError(f"{path} is not valid JSON") from None
    schema_file = Path(core.__file__).parent / "data" / "deployer_pack.schema.json"
    try:
        jsonschema.validate(raw, json.loads(schema_file.read_text(encoding="utf-8")))
    except jsonschema.ValidationError:
        raise VerifyInputError(
            f"{path} is not a valid deployer pack (schema)"
        ) from None

    if raw["integrity"].get("signature") is not None:
        if pub_key is None:
            from opencomplai_cli import main as _main

            pub_key = _main._SIGNING_PUB
        if not pub_key.is_file():
            raise VerifyInputError(f"public key file not found: {pub_key}")
    result = core.verify_pack(raw, pub_key)
    return VerifyResult("deployer-pack", result.status, result.detail)


register_kind("deployer-pack", verify_deployer_pack)
