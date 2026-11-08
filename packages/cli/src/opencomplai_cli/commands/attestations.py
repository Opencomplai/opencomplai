"""CLI: ``opencomplai attestations pull``.

Fetches the attestation bundle from the endpoint configured in
``OPENCOMPLAI_DASHBOARD_URL`` (with ``OPENCOMPLAI_API_KEY``, the pair
``opencomplai push`` uses) and writes it to a file, so a CI job can run
``check --attestations-file`` against a bundle it can pin and replay. Same exit
convention as ``push``: 0 on success, 3 otherwise; it never changes a gate.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape

from opencomplai_cli.attestations import AttestationError, fetch_from_env

console = Console()
err_console = Console(stderr=True)

EXIT_OK = 0
EXIT_PULL_FAILED = 3

app = typer.Typer(help="Attestation bundle commands.")


def run_pull(
    output_file: Path,
    system_id: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> int:
    """Fetch the bundle and write it to ``output_file`` as pretty JSON.

    ``env`` defaults to ``os.environ``; tests pass a synthetic one.
    """
    try:
        bundle = fetch_from_env(system_id, env)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            bundle.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    except (AttestationError, OSError) as exc:
        err_console.print(f"[red]Pull failed:[/red] {escape(str(exc))}")
        return EXIT_PULL_FAILED
    console.print(f"[green]Wrote {escape(str(output_file))}.[/green]")
    console.print(f"  records:   {bundle.count}")
    console.print(f"  issued_at: {escape(bundle.issued_at)}")
    return EXIT_OK


@app.command("pull")
def pull_cmd(
    output_file: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="File to write the attestation bundle to (pretty-printed JSON).",
    ),
    system_id: str | None = typer.Option(
        None,
        "--system-id",
        help=(
            "System the bundle is for. Without it the bundle holds the "
            "organisation-wide records only."
        ),
    ),
) -> None:
    """
    Download the attestation bundle for a system and write it to a file.

    Requires OPENCOMPLAI_API_KEY and OPENCOMPLAI_DASHBOARD_URL, the pair
    `opencomplai push` uses. Plain http is refused for any host other than
    localhost. Feed the file to `opencomplai check --attestations-file`. Exits 0
    on success and 3 otherwise.
    """
    sys.exit(run_pull(output_file, system_id))
