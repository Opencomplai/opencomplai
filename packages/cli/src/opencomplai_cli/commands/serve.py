"""CLI: opencomplai serve — local loopback dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console

err_console = Console(stderr=True)


def run_serve(project_root: Path, host: str, port: int) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        err_console.print(
            "[red]Error:[/red] serve binds to 127.0.0.1/localhost only "
            "(this is not the Pro SaaS dashboard)."
        )
        raise typer.Exit(2)
    try:
        import uvicorn
    except ImportError as exc:
        err_console.print(
            "[red]Error:[/red] Install the serve extra: "
            "pip install 'opencomplai-cli[serve]'"
        )
        raise typer.Exit(2) from exc

    from opencomplai_core.local_dashboard import create_app

    app = create_app(project_root.resolve())
    err_console.print(
        f"[green]OpenComplAI local dashboard[/green] on http://{host}:{port}/ "
        "(loopback only — not Pro/SaaS)"
    )
    uvicorn.run(app, host=host, port=port, log_level="info")
