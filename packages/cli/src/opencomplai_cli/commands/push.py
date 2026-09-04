"""
CLI: ``opencomplai push`` — publish a signed ``compliance-artifact.json`` to
the Opencomplai Premium Dashboard (GO-LIVE CORE-4).

Deliberately a standalone command, not a ``--push`` flag on ``check``/
``scan``: those commands' exit-code semantics are a CI-gating contract
(0/1/2/3/4, see ``main.py``'s module docstring) that must never depend on
network reachability. ``push`` is a separate, opt-in step a pipeline runs
*after* ``check`` has already gated the build locally.

Auth model: API-key, not the CI connectors' JWT/OIDC path. ``push`` sends
no ``install_id`` in its envelope at all -- ``dashboard_ingest.routes``
derives it server-side from the authenticated API key's own project (see
ingest-api's ``test_key_auth.py::test_envelope_install_id_unknown_is
_overridden_by_principal``), and a key-authed request MAY omit
``signature`` entirely since the key itself attests authenticity
(``dashboard_ingest.contract.validate_envelope_shape``'s
``require_install_id=False`` default for this path).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rich.console import Console
from rich.markup import escape

from opencomplai_cli.publish import (
    envelope_signature,
    prepare_dossier_envelope,
    prepare_scan_status_artifact,
    publish_dossier_envelope,
    publish_scan_status,
)

console = Console()
err_console = Console(stderr=True)

EXIT_OK = 0
EXIT_PUBLISH_FAILED = 3

_LOCAL_HOSTNAMES = {"localhost", "127.0.0.1"}


def run_push(artifact_file: Path, *, env: dict[str, str] | None = None) -> int:
    """
    Read ``artifact_file``, shape it, and POST it to the dashboard.

    Returns the process exit code (0 on HTTP 200/201, 3 otherwise) instead
    of calling ``sys.exit`` directly -- same convention as
    ``connectors.github_actions.run_connector`` -- so tests can assert on
    the return value without catching ``SystemExit``. The ``env`` mapping
    defaults to ``os.environ`` and exists for the same reason: tests pass a
    synthetic environment instead of monkeypatching process-global state.
    """
    _env = env if env is not None else os.environ

    if not artifact_file.exists():
        err_console.print(f"[red]Error:[/red] artifact file not found: {artifact_file}")
        err_console.print(
            "Run [bold]opencomplai check --sign[/bold] first to produce one."
        )
        return EXIT_PUBLISH_FAILED

    # A directory path, an unreadable file, or non-UTF-8 bytes must all
    # produce a clean one-line error rather than an uncaught traceback --
    # this is a CLI a pipeline script parses stderr from, not a Python API.
    try:
        raw_text = artifact_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        err_console.print(f"[red]Error:[/red] could not read {artifact_file}: {exc}")
        return EXIT_PUBLISH_FAILED

    try:
        artifact: Any = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Error:[/red] {artifact_file} is not valid JSON: {exc}")
        return EXIT_PUBLISH_FAILED

    if not isinstance(artifact, dict):
        err_console.print(
            f"[red]Error:[/red] {artifact_file} must contain a JSON object "
            "(a ScanStatusArtifact), not a "
            f"{type(artifact).__name__}"
        )
        return EXIT_PUBLISH_FAILED

    api_key = _env.get("OPENCOMPLAI_API_KEY", "")
    dashboard_url = _env.get("OPENCOMPLAI_DASHBOARD_URL", "").rstrip("/")
    if not api_key or not dashboard_url:
        err_console.print(
            "[red]Error:[/red] OPENCOMPLAI_API_KEY and OPENCOMPLAI_DASHBOARD_URL "
            "must both be set."
        )
        return EXIT_PUBLISH_FAILED

    parsed_url = urlparse(dashboard_url)
    if parsed_url.scheme == "http" and parsed_url.hostname not in _LOCAL_HOSTNAMES:
        err_console.print(
            f"[yellow]Warning:[/yellow] OPENCOMPLAI_DASHBOARD_URL ({dashboard_url}) "
            "uses plain http -- the API key will be sent unencrypted over the network. "
            "Use https unless this is local development."
        )

    prepared = prepare_scan_status_artifact(
        artifact, commit_env=_env, repo_dir=artifact_file.resolve().parent
    )

    # No install_id (see module docstring) -- the server derives it from
    # the API key's own project. signature is only forwarded when the
    # mapper changed nothing at all (G-5, see publish.envelope_signature);
    # otherwise it falls back to "" (never null) so the envelope always
    # matches the JSON Schema's string-or-absent shape.
    signature = envelope_signature(artifact, prepared)
    original_signature = artifact.get("signature")
    if (
        isinstance(original_signature, str)
        and original_signature != ""
        and not signature
    ):
        err_console.print(
            "[dim]note: artifact signature not forwarded (mapped payload differs "
            "from signed bytes; the API key attests this push)[/dim]"
        )

    envelope = {
        "system_id": prepared.get("system_id", "unknown"),
        "artifact": prepared,
        "signature": signature,
    }

    status, data = publish_scan_status(dashboard_url, api_key, envelope)

    if status in (200, 201):
        outcome = escape(
            str(data.get("outcome", "accepted" if status == 201 else "replayed"))
        )
        content_hash = escape(str(data.get("content_hash", "")))
        console.print(f"[green]Push {outcome}.[/green]")
        console.print(f"  system_id:    {envelope['system_id']}")
        console.print(f"  content_hash: {content_hash}")
        console.print(f"\nDashboard: {dashboard_url}")
        return EXIT_OK

    # `data` is server-controlled (a JSON error body echoed back to the
    # terminal) -- escaped so it can never inject rich markup.
    err_console.print(f"[red]Push failed ({status}):[/red] {escape(str(data))}")
    return EXIT_PUBLISH_FAILED


def run_push_dossier(dossier_file: Path, *, env: dict[str, str] | None = None) -> int:
    """
    Read ``dossier_file`` (an ``AnnexIVDossier`` JSON -- e.g. the
    ``dossier_<id>.json`` ``opencomplai docs generate`` writes locally),
    shape it into a ``dossier_envelope``, and POST it to the dashboard
    (DG-10).

    Transliterated from ``run_push`` above: same file/env validation, same
    ``http``-non-local warning, same auth model (``ock_`` API key, no
    ``install_id``), same ``(0 success / 3 otherwise)`` return contract.
    Two differences beyond the obvious (path, mapper, transport function):

    * The envelope's own ``signature`` is always ``""``. Unlike a
      ``ScanStatusArtifact``, an ``AnnexIVDossier``'s own ``signature``
      field (when present) signs the *dossier bundle* under a scheme
      unrelated to the ingest envelope's G-5 byte-identity check
      (``envelope_signature``'s docstring) -- forwarding it would not
      "sort of" verify, it would deterministically fail closed. A
      key-authed push already attests via the API key itself, same as
      scan status's own key-authed path (``dashboard_ingest.routes``).
    * The error message on a missing file points at ``docs generate``
      instead of ``check --sign``.
    """
    _env = env if env is not None else os.environ

    if not dossier_file.exists():
        err_console.print(f"[red]Error:[/red] dossier file not found: {dossier_file}")
        err_console.print(
            "Run [bold]opencomplai docs generate[/bold] first to produce one."
        )
        return EXIT_PUBLISH_FAILED

    try:
        raw_text = dossier_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        err_console.print(f"[red]Error:[/red] could not read {dossier_file}: {exc}")
        return EXIT_PUBLISH_FAILED

    try:
        dossier: Any = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        err_console.print(f"[red]Error:[/red] {dossier_file} is not valid JSON: {exc}")
        return EXIT_PUBLISH_FAILED

    if not isinstance(dossier, dict):
        err_console.print(
            f"[red]Error:[/red] {dossier_file} must contain a JSON object "
            "(an AnnexIVDossier), not a "
            f"{type(dossier).__name__}"
        )
        return EXIT_PUBLISH_FAILED

    api_key = _env.get("OPENCOMPLAI_API_KEY", "")
    dashboard_url = _env.get("OPENCOMPLAI_DASHBOARD_URL", "").rstrip("/")
    if not api_key or not dashboard_url:
        err_console.print(
            "[red]Error:[/red] OPENCOMPLAI_API_KEY and OPENCOMPLAI_DASHBOARD_URL "
            "must both be set."
        )
        return EXIT_PUBLISH_FAILED

    parsed_url = urlparse(dashboard_url)
    if parsed_url.scheme == "http" and parsed_url.hostname not in _LOCAL_HOSTNAMES:
        err_console.print(
            f"[yellow]Warning:[/yellow] OPENCOMPLAI_DASHBOARD_URL ({dashboard_url}) "
            "uses plain http -- the API key will be sent unencrypted over the network. "
            "Use https unless this is local development."
        )

    prepared = prepare_dossier_envelope(
        dossier, commit_env=_env, repo_dir=dossier_file.resolve().parent
    )

    envelope = {
        "system_id": prepared.get("system_id", "unknown"),
        "artifact": prepared,
        "signature": "",
    }

    status, data = publish_dossier_envelope(dashboard_url, api_key, envelope)

    if status in (200, 201):
        outcome = escape(
            str(data.get("outcome", "accepted" if status == 201 else "replayed"))
        )
        content_hash = escape(str(data.get("content_hash", "")))
        console.print(f"[green]Push {outcome}.[/green]")
        console.print(f"  system_id:    {envelope['system_id']}")
        console.print(f"  content_hash: {content_hash}")
        console.print(f"\nDashboard: {dashboard_url}")
        return EXIT_OK

    err_console.print(f"[red]Push failed ({status}):[/red] {escape(str(data))}")
    return EXIT_PUBLISH_FAILED


__all__ = [
    "EXIT_OK",
    "EXIT_PUBLISH_FAILED",
    "run_push",
    "run_push_dossier",
]
