"""
Opencomplai CLI entrypoint.

Exit codes (contractual — never deviate):
  0  PASS            — all critical controls passed
  1  CONTROL_FAIL    — one or more critical controls failed
  2  VALIDATION_FAIL — manifest or input validation error
  3  POLICY_BLOCK    — egress or policy enforcement blocked the operation
  4  TRAP_DETECTED   — substantial modification or profiling trap triggered
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from enum import StrEnum
from pathlib import Path

import typer
from opencomplai_core.engine import assess
from opencomplai_core.eval_engine import eval_summary_from_report, run_evals
from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.principle_report import build_principle_summary
from opencomplai_core.models import (
    AssessmentInput,
    CorroborationReport,
    DiscrepancySeverity,
    EvalSampleSet,
    EvalSummary,
    EvaluatorOutcome,
    GapReport,
    GapStatus,
    ModelMetadata,
    RiskLevel,
    ScanResult,
    ScanStatusArtifact,
    ScanSummary,
    SystemManifest,
)
from opencomplai_core.output_envelope import wrap_scan_output
from opencomplai_core.recommend_engine import render_recommendations
from opencomplai_core.report_engine import render_report
from opencomplai_core.scan_engine import run_scan, scan_summary_from_report
from opencomplai_core.scanner.feature_types import ScanConfig, ScanProgressCallback
from opencomplai_core.scanner.ocignore import ensure_ocignore
from opencomplai_core.scanner.registry import DETECTOR_REGISTRY
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from opencomplai_cli import (
    PROJECT_AUTHOR,
    PROJECT_AUTHOR_EMAIL,
    PROJECT_DOCS_URL,
    PROJECT_HOMEPAGE,
    PROJECT_LICENSE,
    PROJECT_TAGLINE,
    SUITE_PACKAGES,
    __version__,
)

app = typer.Typer(
    name="opencomplai",
    help=(
        "Opencomplai — Open-source AI compliance for a trustworthy future.\n\n"
        "Automated risk assessment, evidence generation, and CI/CD-native "
        "compliance checks for AI engineering teams."
    ),
    add_completion=False,
)
risk_app = typer.Typer(help="Risk classification commands.")
docs_app = typer.Typer(help="Documentation generation commands.")
sync_app = typer.Typer(help="Metadata sync commands.")
keys_app = typer.Typer(
    help="Signing key management (ISO 27001 A.8.24 / FedRAMP SC-12)."
)

from opencomplai_cli.commands.checker import (  # noqa: E402
    build_checker_session_ref,
    display_results,
    evaluate_and_finalize,
    load_answers_file,
    run_interactive_wizard,
    write_exports,
)
from opencomplai_cli.commands.dashboard import app as dashboard_app  # noqa: E402
from opencomplai_cli.commands.interactive_init import run_interactive_init  # noqa: E402
from opencomplai_cli.commands.serve import run_serve  # noqa: E402

ai_app = typer.Typer(help="AI intent analysis commands.")

app.add_typer(risk_app, name="risk")
app.add_typer(docs_app, name="docs")
app.add_typer(sync_app, name="sync")
app.add_typer(dashboard_app, name="dashboard")
app.add_typer(keys_app, name="keys")
app.add_typer(ai_app, name="ai")

console = Console()
err_console = Console(stderr=True)

_OPENCOMPLAI_DIR = Path.home() / ".opencomplai"
_CONFIG_FILE = _OPENCOMPLAI_DIR / "config.yaml"
_SIGNING_KEY = _OPENCOMPLAI_DIR / "signing.key"
_SIGNING_PUB = _OPENCOMPLAI_DIR / "signing.pub"


class OutputFormat(StrEnum):
    """CLI output format."""

    human = "human"
    json = "json"


class FailOnLevel(StrEnum):
    """Opt-in CI gating for code corroboration scans."""

    none = "none"
    new_major = "new-major"
    major = "major"
    critical = "critical"


# ---------------------------------------------------------------------------
# Version & package metadata
# ---------------------------------------------------------------------------


def _resolve_version(dist_name: str = "opencomplai") -> str:
    """Installed version of *dist_name*, falling back to the bundled default."""
    try:
        return importlib.metadata.version(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return __version__


def _dep_name(requirement: str) -> str:
    """Extract the bare distribution name from a requirement specifier."""
    return re.split(r"[<>=!~;\[ (]", requirement, maxsplit=1)[0].strip()


def _reverse_dependencies(dist_name: str) -> list[str]:
    """Installed distributions that declare a runtime dependency on *dist_name*.

    Mirrors pip's ``Required-by``: only unconditional runtime requirements
    count (dependencies gated behind an ``extra`` marker are ignored).
    """
    target = dist_name.replace("-", "_").lower()
    dependents: set[str] = set()
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        if not name:
            continue
        for requirement in dist.requires or []:
            if "extra ==" in requirement:
                continue
            if _dep_name(requirement).replace("-", "_").lower() == target:
                dependents.add(name)
                break
    return sorted(dependents)


def _distribution_info(dist_name: str) -> dict:
    """pip-show-style metadata for one Opencomplai distribution.

    Home page, author, e-mail and licence come from the canonical constants
    in :mod:`opencomplai_cli`, so the output is always complete regardless of
    how (or whether) the package was installed.
    """
    info: dict = {
        "name": dist_name,
        "version": _resolve_version(dist_name),
        "summary": "",
        "home_page": PROJECT_HOMEPAGE,
        "author": PROJECT_AUTHOR,
        "author_email": PROJECT_AUTHOR_EMAIL,
        "license": PROJECT_LICENSE,
        "location": "",
        "requires": [],
        "required_by": [],
        "installed": False,
    }
    try:
        dist = importlib.metadata.distribution(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return info

    info["installed"] = True
    info["summary"] = dist.metadata["Summary"] or ""
    requires: list[str] = []
    for requirement in dist.requires or []:
        if "extra ==" in requirement:
            continue
        name = _dep_name(requirement)
        if name and name not in requires:
            requires.append(name)
    info["requires"] = requires
    info["required_by"] = _reverse_dependencies(dist_name)
    try:
        info["location"] = str(Path(str(dist.locate_file(""))).resolve())
    except Exception:
        info["location"] = ""
    return info


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"opencomplai {_resolve_version()}")
        raise typer.Exit()


@app.callback()
def _main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        is_eager=True,
        callback=_version_callback,
        help="Show the Opencomplai version and exit.",
    ),
) -> None:
    """
    Opencomplai — Open-source AI compliance for a trustworthy future.

    Automated risk assessment, evidence generation, and CI/CD-native
    compliance checks for AI engineering teams.
    """


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _load_config() -> dict:
    """Load ~/.opencomplai/config.yaml; return empty dict if absent."""
    if not _CONFIG_FILE.exists():
        return {}
    try:
        text = _CONFIG_FILE.read_text()
        cfg: dict = {}
        for line in text.splitlines():
            m = re.match(r"^(\w+):\s*(.+)$", line.strip())
            if m:
                cfg[m.group(1)] = m.group(2).strip()
        return cfg
    except Exception:
        return {}


def _write_config(cfg: dict) -> None:
    _OPENCOMPLAI_DIR.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}: {v}" for k, v in cfg.items()]
    _CONFIG_FILE.write_text("\n".join(lines) + "\n")


def _get_install_id() -> str:
    cfg = _load_config()
    return cfg.get("install_id", str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Service communication
# ---------------------------------------------------------------------------


def _call_service(path: str, payload: dict) -> tuple[int, dict]:
    base_url = os.environ.get("OPENCOMPLAI_API_URL", "").rstrip("/")
    if not base_url:
        raise ConnectionError("OPENCOMPLAI_API_URL not set — using local engine")
    url = f"{base_url}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())
    except Exception as exc:
        raise ConnectionError(f"Service call failed: {exc}") from exc


def _emit_event(
    event_type: str, payload: dict, signer_id: str | None = None
) -> str | None:
    """Append a ledger event; return event_id or None on failure."""
    try:
        _, data = _call_service(
            "/v1/evidence/events",
            {"event_type": event_type, "payload": payload, "signer_id": signer_id},
        )
        return data.get("event_id")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# ScanStatusArtifact helpers
# ---------------------------------------------------------------------------


def _result_from_risk(
    risk_class: str, trap_detected: bool, profiling_detected: bool
) -> ScanResult:
    if trap_detected:
        return ScanResult.TRAP_DETECTED
    if risk_class == "unacceptable":
        return ScanResult.POLICY_BLOCK
    if risk_class in ("high", "limited"):
        return ScanResult.CONTROL_FAIL
    return ScanResult.PASS


def _controls_from_risk(
    risk_class: str, trap_detected: bool, profiling_detected: bool
) -> list[str]:
    controls: list[str] = []
    if trap_detected:
        controls.append("EU_AIA_ART25_MODIFICATION_TRAP")
    if profiling_detected:
        controls.append("EU_AIA_ART6_PROFILING")
    if risk_class in ("high", "unacceptable"):
        controls.append("EU_AIA_ART6_HIGH_RISK")
    return controls


def _result_from_local(risk_result) -> tuple[ScanResult, list[str]]:
    failed_ids = [r.rule_id for r in risk_result.rule_results if not r.passed]
    if "EU_AIA_ART25_MODIFICATION_TRAP" in failed_ids:
        return ScanResult.TRAP_DETECTED, failed_ids
    if risk_result.risk_level == RiskLevel.UNACCEPTABLE:
        return ScanResult.POLICY_BLOCK, failed_ids
    if risk_result.rules_failed > 0:
        return ScanResult.CONTROL_FAIL, failed_ids
    return ScanResult.PASS, failed_ids


def _exit_code(result: ScanResult, scan_mode: str) -> int:
    mapping = {
        ScanResult.PASS: 0,
        ScanResult.CONTROL_FAIL: 1,
        ScanResult.VALIDATION_FAIL: 2,
        ScanResult.POLICY_BLOCK: 3,
        ScanResult.TRAP_DETECTED: 4,
        ScanResult.DEGRADED_COMPLETE: 1 if scan_mode == "ci" else 0,
    }
    return mapping.get(result, 1)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("version")
def version_cmd(
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Show the installed Opencomplai version."""
    version = _resolve_version()
    if output == OutputFormat.json:
        console.print_json(json.dumps({"name": "opencomplai", "version": version}))
    else:
        console.print(f"opencomplai {version}")


@app.command("info")
def info_cmd(
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """
    Show full package metadata — a complete replacement for `pip show opencomplai`.

    Prints name, version, summary, home page, author, licence, install
    location and the dependency graph for the Opencomplai suite, with every
    field populated.
    """
    roles = dict(SUITE_PACKAGES)
    primary = _distribution_info("opencomplai")
    suite = [_distribution_info(name) for name, _role in SUITE_PACKAGES]

    if output == OutputFormat.json:
        console.print_json(json.dumps({**primary, "suite": suite}, indent=2))
        return

    console.print(f"\n[bold]Opencomplai[/bold] — {PROJECT_TAGLINE}\n")

    def _field(label: str, value: str) -> None:
        console.print(f"  [dim]{label:<13}[/dim] {value}")

    summary = primary["summary"] or "Opencomplai Python SDK for EU AI Act compliance"
    _field("Name:", primary["name"])
    _field("Version:", primary["version"])
    _field("Summary:", summary)
    _field("Home-page:", primary["home_page"])
    _field("Author:", primary["author"])
    _field("Author-email:", primary["author_email"])
    _field("License:", primary["license"])
    _field("Location:", primary["location"] or "(not installed)")
    _field("Requires:", ", ".join(primary["requires"]) or "(none)")
    _field("Required-by:", ", ".join(primary["required_by"]) or "(none)")

    table = Table(
        title="\nOpencomplai suite",
        title_justify="left",
        show_header=True,
        header_style="bold",
    )
    table.add_column("Package", style="cyan")
    table.add_column("Version")
    table.add_column("Role", style="dim")
    table.add_column("Installed")
    for pkg in suite:
        installed = "[green]yes[/green]" if pkg["installed"] else "[red]no[/red]"
        table.add_row(
            pkg["name"], pkg["version"], roles.get(pkg["name"], ""), installed
        )
    console.print(table)
    console.print(
        f"\n  [dim]Docs: {PROJECT_HOMEPAGE}  ·  License: {PROJECT_LICENSE}[/dim]\n"
    )


@app.command("init")
def init_cmd(
    system_id: str | None = typer.Option(
        None, "--system-id", help="Unique system identifier"
    ),
    intended_purpose: str | None = typer.Option(
        None,
        "--intended-purpose",
        help="Primary intended purpose (maps to Annex III categories)",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Run EU AI Act applicability checker wizard, then prompt for manifest fields",
    ),
    skip_checker: bool = typer.Option(
        False,
        "--skip-checker",
        help="With --interactive, skip the applicability checker wizard",
    ),
    compliance_target: str = typer.Option("EU_AI_ACT", "--compliance-target"),
    high_risk_presumption: bool = typer.Option(
        False, "--high-risk-presumption/--no-high-risk-presumption"
    ),
    training_data_description: str | None = typer.Option(
        None,
        "--training-data-description",
        help=(
            "Annex IV Section 2: free-text summary of training data sources "
            "and curation. REQUIRED for HIGH-risk systems."
        ),
    ),
    model_architecture: str | None = typer.Option(
        None,
        "--model-architecture",
        help=(
            "Annex IV Section 2: free-text architecture description. "
            "REQUIRED for HIGH-risk systems."
        ),
    ),
    monitoring_approach: str | None = typer.Option(
        None,
        "--monitoring-approach",
        help="Annex IV Section 3: how the system is monitored in production.",
    ),
    incident_response_procedure: str | None = typer.Option(
        None,
        "--incident-response-procedure",
        help="Annex IV Section 3: incident-response pointer or summary.",
    ),
    section_extras_file: Path | None = typer.Option(
        None,
        "--section-extras-file",
        help=(
            "Path to a JSON file with structured Section 2/3 inputs "
            "(performance_metrics, known_limitations, human_oversight_measures). "
            "Merged into the manifest. See docs/customer-workflow for the schema."
        ),
    ),
    output_file: Path = typer.Option(Path("system-manifest.json"), "--output", "-o"),
    run_code_scan: bool = typer.Option(
        False, "--scan", help="Run code corroboration after writing manifest"
    ),
    repo_root: Path = typer.Option(Path("."), "--repo-root"),
) -> None:
    """
    Initialise compliance tooling and create a system manifest.

    Sets up ~/.opencomplai/ (Ed25519 signing keypair + config) on first run,
    then writes a system manifest to --output.

    HIGH-risk systems MUST populate Section 2 (training data, architecture)
    and SHOULD populate Section 3 (oversight, monitoring) — either via the
    inline flags above or with --section-extras-file.
    """
    if interactive:
        extras: dict = {}
        if section_extras_file is not None:
            if not section_extras_file.exists():
                err_console.print(
                    f"[red]Error:[/red] --section-extras-file not found: {section_extras_file}"
                )
                sys.exit(2)
            try:
                extras = json.loads(section_extras_file.read_text())
            except json.JSONDecodeError as exc:
                err_console.print(
                    f"[red]Error parsing --section-extras-file:[/red] {exc}"
                )
                sys.exit(2)
        if not _SIGNING_KEY.exists():
            try:
                from opencomplai_core.signing import generate_keypair

                install_id = generate_keypair(_OPENCOMPLAI_DIR)
                existing_cfg = _load_config()
                existing_cfg["install_id"] = install_id
                _write_config(existing_cfg)
                console.print(
                    f"[green]Signing keypair generated[/green] → {_OPENCOMPLAI_DIR}"
                )
            except ImportError:
                console.print(
                    "[yellow]cryptography not installed — signing disabled.[/yellow]"
                )
        run_interactive_init(
            skip_checker=skip_checker,
            output_file=output_file,
            compliance_target=compliance_target,
            section_extras=extras or None,
            signing_setup_fn=None,
        )
        return

    if not system_id or not intended_purpose:
        err_console.print(
            "[red]Error:[/red] --system-id and --intended-purpose are required "
            "(or use --interactive)."
        )
        sys.exit(2)

    # --- Tool setup (idempotent) ---
    if not _SIGNING_KEY.exists():
        try:
            from opencomplai_core.signing import generate_keypair

            install_id = generate_keypair(_OPENCOMPLAI_DIR)
            existing_cfg = _load_config()
            existing_cfg["install_id"] = install_id
            existing_cfg["gateway_url"] = os.environ.get(
                "OPENCOMPLAI_API_URL", "http://localhost:8080"
            )
            _write_config(existing_cfg)
            console.print(
                f"[green]Signing keypair generated[/green] → {_OPENCOMPLAI_DIR}"
            )
            console.print(f"  install_id: {install_id}")
        except ImportError:
            install_id = str(uuid.uuid4())
            existing_cfg = _load_config()
            if "install_id" not in existing_cfg:
                existing_cfg["install_id"] = install_id
                _write_config(existing_cfg)
            console.print(
                "[yellow]cryptography not installed — signing disabled. "
                "Run: pip install cryptography[/yellow]"
            )
    else:
        console.print(
            f"[dim]Signing keypair already exists at {_OPENCOMPLAI_DIR}[/dim]"
        )

    # --- Optional structured extras (Section 2/3 fields too unwieldy for flags) ---
    extras: dict = {}
    if section_extras_file is not None:
        if not section_extras_file.exists():
            err_console.print(
                f"[red]Error:[/red] --section-extras-file not found: {section_extras_file}"
            )
            sys.exit(2)
        try:
            extras = json.loads(section_extras_file.read_text())
            if not isinstance(extras, dict):
                raise ValueError("extras file must contain a JSON object at top level")
        except (json.JSONDecodeError, ValueError) as exc:
            err_console.print(f"[red]Error parsing --section-extras-file:[/red] {exc}")
            sys.exit(2)

    # --- System manifest ---
    manifest_kwargs: dict = {
        "system_id": system_id,
        "intended_purpose": intended_purpose,
        "compliance_target": compliance_target,
        "high_risk_presumption": high_risk_presumption,
        "commit_ref": "HEAD",
        "training_data_description": training_data_description,
        "model_architecture": model_architecture,
        "monitoring_approach": monitoring_approach,
        "incident_response_procedure": incident_response_procedure,
    }
    # Inline flags win over the extras file when both are supplied.
    for key in (
        "performance_metrics",
        "known_limitations",
        "human_oversight_measures",
    ):
        if key in extras:
            manifest_kwargs[key] = extras[key]
    for key, value in extras.items():
        if key not in manifest_kwargs or manifest_kwargs.get(key) is None:
            manifest_kwargs[key] = value

    try:
        manifest = SystemManifest(**manifest_kwargs)
    except Exception as exc:
        err_console.print(f"[red]Invalid manifest input:[/red] {exc}")
        sys.exit(2)

    output_file.write_text(manifest.model_dump_json(indent=2))
    console.print(f"[green]Manifest written to {output_file}[/green]")
    console.print(f"  system_id:         {manifest.system_id}")
    console.print(f"  intended_purpose:  {manifest.intended_purpose}")
    console.print(f"  compliance_target: {manifest.compliance_target}")
    if high_risk_presumption and not (
        manifest.training_data_description and manifest.model_architecture
    ):
        console.print(
            "\n[yellow]Warning:[/yellow] high_risk_presumption is set but Annex IV "
            "Section 2 fields (training_data_description, model_architecture) are "
            "missing. The resulting dossier will misrepresent the system to an auditor."
        )
    if run_code_scan:
        scan_config = _bootstrap_ocignore(repo_root, ocignore_path=None, bootstrap=True)
        _, report, _ = _run_scan_corroboration(
            manifest,
            manifest.commit_ref,
            repo_root,
            emit_evidence=False,
            scan_config=scan_config,
        )
        _print_scan_human(report)
        if report.discrepancies:
            console.print(
                "\n[yellow]Confirm or update --intended-purpose before committing.[/yellow]"
            )
    else:
        console.print(
            "\nNext step: run [bold]opencomplai check[/bold] to assess compliance."
        )


def _checker_web(*, local: bool) -> None:
    """Open the browser-based checker — hosted page or local server."""
    import webbrowser

    hosted_url = os.environ.get(
        "OPENCOMPLAI_DOCS_URL",
        f"{PROJECT_DOCS_URL}/getting-started/eu-ai-act-checker/",
    )

    if not local:
        console.print(f"Opening checker: [link]{hosted_url}[/link]")
        webbrowser.open(hosted_url)
        return

    # --local: serve the pre-built widget HTML from package data
    import http.server
    import importlib.resources
    import socket
    import threading

    # Locate the bundled standalone HTML (installed as package data)
    try:
        pkg_files = importlib.resources.files("opencomplai_cli")
        html_path = pkg_files / "data" / "checker-local.html"
        html_bytes = html_path.read_bytes()
    except (FileNotFoundError, TypeError):
        err_console.print(
            "[red]Local checker not bundled.[/red] "
            "Run the docs build first or use [bold]opencomplai checker --web[/bold] "
            "to open the hosted page."
        )
        sys.exit(1)

    # Pick a free port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.startswith("/__ococ_shutdown"):
                self._respond_shutdown()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_bytes)

        def do_POST(self) -> None:
            if self.path.startswith("/__ococ_shutdown"):
                self._respond_shutdown()
                return
            self.send_response(404)
            self.end_headers()

        def _respond_shutdown(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"stopping")
            # serve_forever() can't be stopped from inside its own
            # request-handling call stack — shut down from another thread.
            threading.Thread(target=server.shutdown, daemon=True).start()

        def log_message(self, *_args: object) -> None:
            pass  # suppress request logs

    server = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    local_url = f"http://127.0.0.1:{port}/?local=1"
    console.print(f"Serving checker locally: [link]{local_url}[/link]")
    console.print(
        "Press [bold]Ctrl+C[/bold], or use the Stop button on the page, to stop."
    )
    webbrowser.open(local_url)
    try:
        thread.join()
    except KeyboardInterrupt:
        server.shutdown()


@app.command("checker")
def checker_cmd(
    answers_file: Path | None = typer.Option(
        None, "--answers", help="JSON file with checker answers (non-interactive)"
    ),
    entity_type: str | None = typer.Option(
        None, "--entity-type", help="Skip E1 prompt when re-running for another role"
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
    export_json: Path | None = typer.Option(None, "--export-json"),
    export_md: Path | None = typer.Option(None, "--export-md"),
    export_pdf: Path | None = typer.Option(None, "--export-pdf"),
    export_all_base: Path | None = typer.Option(
        None, "--export-all", help="Base path without extension for .json/.md/.pdf"
    ),
    write_manifest: Path | None = typer.Option(
        None, "--write-manifest", help="Write bridged fields into manifest at this path"
    ),
    web: bool = typer.Option(
        False, "--web", help="Open the browser-based checker on the docs site"
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="With --web: serve the checker locally instead of opening the hosted page",
    ),
) -> None:
    """
    Run the EU AI Act applicability checker (checker version v2025-07-28).

    Interactive by default; pass --answers for CI replay. Export with --export-* flags.
    Use --web to open the browser-based checker; add --local to serve it offline.
    """
    if web:
        _checker_web(local=local)
        return

    from opencomplai_core.compliance_checker import (
        bridge_to_manifest_fields,
    )

    if answers_file is not None:
        session = load_answers_file(answers_file)
    else:
        session = run_interactive_wizard(skip_allowed=False)
        if session is None:
            sys.exit(0)

    if entity_type:
        session.answers["e1_entity_type"] = entity_type

    result = evaluate_and_finalize(session)

    if output == OutputFormat.json:
        console.print_json(result.model_dump_json(indent=2))
    else:
        display_results(result)

    write_exports(
        result,
        export_json=export_json,
        export_md=export_md,
        export_pdf=export_pdf,
        export_all_base=export_all_base,
    )

    if write_manifest is not None:
        bridged = bridge_to_manifest_fields(result)
        report_path = export_json or (
            export_all_base.with_suffix(".json") if export_all_base else None
        )
        payload: dict = {
            "system_id": typer.prompt("System ID", default="my-ai-system"),
            "intended_purpose": bridged["intended_purpose"],
            "compliance_target": "EU_AI_ACT",
            "high_risk_presumption": bridged["high_risk_presumption"],
            "commit_ref": "HEAD",
            "operator_role": bridged["operator_role"],
            "checker_session": build_checker_session_ref(result, report_path),
        }
        write_manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"[green]Manifest written to[/green] {write_manifest}")


@app.command("validate-manifest")
def validate_manifest_cmd(
    manifest_file: Path = typer.Argument(..., help="Path to system manifest JSON file"),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Validate a system manifest against the required schema."""
    if not manifest_file.exists():
        err_console.print(f"[red]Error:[/red] manifest file not found: {manifest_file}")
        err_console.print(
            "Tip: run [bold]opencomplai init --system-id <id> --intended-purpose <purpose>[/bold] first."
        )
        sys.exit(2)
    try:
        data = json.loads(manifest_file.read_text())
        manifest = SystemManifest.model_validate(data)
    except Exception as e:
        err_console.print(f"[red]Validation error:[/red] {e}")
        sys.exit(2)

    if output == OutputFormat.json:
        console.print_json(manifest.model_dump_json(indent=2))
    else:
        console.print("[green]Manifest is valid.[/green]")
        console.print(f"  system_id:             {manifest.system_id}")
        console.print(f"  intended_purpose:      {manifest.intended_purpose}")
        console.print(f"  compliance_target:     {manifest.compliance_target}")
        console.print(f"  high_risk_presumption: {manifest.high_risk_presumption}")


def _load_sample_set(
    path: Path | None, manifest: SystemManifest
) -> EvalSampleSet | None:
    if path is None:
        return None
    if not path.exists():
        err_console.print(f"[red]Error:[/red] sample set not found: {path}")
        sys.exit(2)
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        err_console.print(
            f"[red]Error:[/red] sample set file is empty: {path}\n"
            "  Make sure the file contains a valid EvalSampleSet JSON object."
        )
        sys.exit(2)
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        err_console.print(
            f"[red]Error:[/red] sample set is not valid JSON: {e}\n  File: {path}"
        )
        sys.exit(2)
    try:
        sample = EvalSampleSet.model_validate(raw)
    except Exception as e:
        err_console.print(f"[red]Sample set validation error:[/red] {e}")
        sys.exit(2)
    if sample.system_id != manifest.system_id:
        err_console.print(
            f"[red]Error:[/red] sample set system_id '{sample.system_id}' "
            f"must match manifest system_id '{manifest.system_id}'"
        )
        sys.exit(2)
    return sample


_GAP_STATUS_STYLE = {
    GapStatus.MET: "[green]MET[/green]",
    GapStatus.PARTIAL: "[yellow]PARTIAL[/yellow]",
    GapStatus.MISSING: "[red]MISSING[/red]",
    GapStatus.UNVERIFIED: "[dim]UNVERIFIED[/dim]",
}


@app.command("gaps")
def gaps_cmd(
    manifest_file: Path = typer.Option(
        Path("system-manifest.json"),
        "--manifest",
        "-m",
        help="Path to system manifest JSON file",
    ),
    commit_ref: str = typer.Option("HEAD", "--commit-ref", help="Git commit reference"),
    scan_report_file: Path | None = typer.Option(
        None,
        "--scan-report",
        help="Path to a CorroborationReport JSON file from a prior `opencomplai scan --output json`",
    ),
    sample_set_file: Path | None = typer.Option(
        None,
        "--sample-set",
        help="Path to EvalSampleSet JSON for safety/bias/leakage evaluators",
    ),
    repo_root: Path = typer.Option(
        Path("."),
        "--repo-root",
        help="Repository root for artifact path probes (Arts. 9/13/14/16/24/43)",
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """
    Print a per-article EU AI Act gap report (Met/Partial/Missing/Unverified).

    Purely a projection of already-computed rule/obligation/scan/eval results —
    informational only, never gates CI (see `opencomplai check` for the CI gate).
    """
    if not manifest_file.exists():
        err_console.print(f"[red]Error:[/red] manifest file not found: {manifest_file}")
        err_console.print("Run [bold]opencomplai init[/bold] first.")
        sys.exit(2)

    try:
        manifest = SystemManifest.model_validate(json.loads(manifest_file.read_text()))
    except Exception as e:
        err_console.print(f"[red]Validation error:[/red] {e}")
        sys.exit(2)

    assessment_input = AssessmentInput(
        model=ModelMetadata(
            name=manifest.system_id,
            version=commit_ref,
            modality="text",
            use_case=manifest.intended_purpose,
            deployment_context="local",
        )
    )
    risk_result = assess(assessment_input)

    corroboration_report = None
    if scan_report_file is not None:
        if not scan_report_file.exists():
            err_console.print(f"[red]Error:[/red] scan report not found: {scan_report_file}")
            sys.exit(2)
        corroboration_report = CorroborationReport.model_validate(
            json.loads(scan_report_file.read_text())
        )

    eval_report = None
    sample_set = _load_sample_set(sample_set_file, manifest)
    if sample_set is not None:
        sample_set = sample_set.model_copy(update={"commit_ref": commit_ref})
        eval_report = run_evals(manifest.system_id, commit_ref, sample_set)

    report = build_gap_report(
        system_id=manifest.system_id,
        commit_ref=commit_ref,
        risk_result=risk_result,
        corroboration_report=corroboration_report,
        eval_report=eval_report,
        repo_root=repo_root.resolve(),
    )
    principle_summary = build_principle_summary(report)
    report = report.model_copy(update={"principle_summary": principle_summary})

    if output == OutputFormat.json:
        envelope = wrap_scan_output(
            json.loads(report.model_dump_json()),
            scan_errors=[],
            tool_version=__version__,
        )
        console.print_json(envelope.model_dump_json(indent=2))
        return

    console.print(f"\n[bold]Opencomplai Gap Report[/bold] — {manifest.system_id}\n")
    console.print(
        "[dim]Statuses are heuristic estimates — not a legal determination.[/dim]\n"
    )
    table = Table(show_header=True, header_style="bold")
    table.add_column("Article", style="dim")
    table.add_column("Status", min_width=10)
    table.add_column("Source", style="dim")
    table.add_column("Evidence", style="dim")
    table.add_column("Rationale")
    for row in report.articles:
        table.add_row(
            row.article,
            _GAP_STATUS_STYLE[row.status],
            row.source.value,
            row.evidence_ref,
            row.rationale,
        )
    console.print(table)

    console.print("\n[bold]Principle Summary[/bold]\n")
    principle_table = Table(show_header=True, header_style="bold")
    principle_table.add_column("Principle", style="dim")
    principle_table.add_column("Status", min_width=10)
    principle_table.add_column("Articles", style="dim")
    for p in principle_summary.principles:
        principle_table.add_row(
            p.title, _GAP_STATUS_STYLE[p.status], ", ".join(p.articles)
        )
    console.print(principle_table)

    console.print(
        "\n[dim]Gap report is informational only — it does not gate CI. "
        "See `opencomplai check` for the compliance-artifact.json CI contract.[/dim]\n"
    )


@app.command("recommend")
def recommend_cmd(
    manifest_file: Path = typer.Option(
        Path("system-manifest.json"),
        "--manifest",
        "-m",
        help="Path to system manifest JSON file (used when --gap-report is not supplied)",
    ),
    commit_ref: str = typer.Option("HEAD", "--commit-ref", help="Git commit reference"),
    gap_report_file: Path | None = typer.Option(
        None,
        "--gap-report",
        help="Path to a GapReport JSON file from a prior `opencomplai gaps --output json`",
    ),
    scan_report_file: Path | None = typer.Option(
        None,
        "--scan-report",
        help="Path to a CorroborationReport JSON file (only used when --gap-report is not supplied)",
    ),
    sample_set_file: Path | None = typer.Option(
        None,
        "--sample-set",
        help="Path to EvalSampleSet JSON (only used when --gap-report is not supplied)",
    ),
    output_dir: Path = typer.Option(
        Path("./fixes"), "--output", "-o", help="Directory to write remediation templates to"
    ),
) -> None:
    """
    Write copy-paste remediation templates for every Missing/Partial gap-report row.

    Templates are static content generation, mapped 1:1 to `opencomplai gaps` article
    rows — no code execution, no network calls, no interaction with signing/evidence.
    """
    if gap_report_file is not None:
        if not gap_report_file.exists():
            err_console.print(f"[red]Error:[/red] gap report not found: {gap_report_file}")
            sys.exit(2)
        report = GapReport.model_validate(json.loads(gap_report_file.read_text()))
    else:
        if not manifest_file.exists():
            err_console.print(f"[red]Error:[/red] manifest file not found: {manifest_file}")
            err_console.print("Run [bold]opencomplai init[/bold] first, or pass --gap-report.")
            sys.exit(2)
        try:
            manifest = SystemManifest.model_validate(json.loads(manifest_file.read_text()))
        except Exception as e:
            err_console.print(f"[red]Validation error:[/red] {e}")
            sys.exit(2)

        assessment_input = AssessmentInput(
            model=ModelMetadata(
                name=manifest.system_id,
                version=commit_ref,
                modality="text",
                use_case=manifest.intended_purpose,
                deployment_context="local",
            )
        )
        risk_result = assess(assessment_input)

        corroboration_report = None
        if scan_report_file is not None:
            if not scan_report_file.exists():
                err_console.print(f"[red]Error:[/red] scan report not found: {scan_report_file}")
                sys.exit(2)
            corroboration_report = CorroborationReport.model_validate(
                json.loads(scan_report_file.read_text())
            )

        eval_report = None
        sample_set = _load_sample_set(sample_set_file, manifest)
        if sample_set is not None:
            sample_set = sample_set.model_copy(update={"commit_ref": commit_ref})
            eval_report = run_evals(manifest.system_id, commit_ref, sample_set)

        report = build_gap_report(
            system_id=manifest.system_id,
            commit_ref=commit_ref,
            risk_result=risk_result,
            corroboration_report=corroboration_report,
            eval_report=eval_report,
        )

    written = render_recommendations(report, output_dir)

    if not written:
        console.print(
            "[green]No Missing/Partial gap-report rows — nothing to recommend.[/green]"
        )
        return

    console.print(f"[bold]Wrote {len(written)} remediation template(s) to {output_dir}[/bold]")
    for path in written:
        console.print(f"  {path}")


@app.command("report")
def report_cmd(
    manifest_file: Path = typer.Option(
        Path("system-manifest.json"),
        "--manifest",
        "-m",
        help="Path to system manifest JSON file",
    ),
    artifact_file: Path | None = typer.Option(
        Path("compliance-artifact.json"),
        "--artifact",
        help="Path to a compliance-artifact.json (ScanStatusArtifact) — optional",
    ),
    gap_report_file: Path | None = typer.Option(
        None,
        "--gap-report",
        help="Path to a GapReport JSON file (overrides any gap_report embedded in --artifact)",
    ),
    output_file: Path = typer.Option(
        Path("report.html"), "--output", "-o", help="Output path (.html or .pdf)"
    ),
) -> None:
    """
    Render a single shareable report combining manifest + rule results + gap report +
    eval/scan summaries.

    Air-gap compatible: reads only local files, makes no network calls, and does not
    replace the Annex IV dossier (`opencomplai docs generate`) or the CI gate
    (`opencomplai check`).
    """
    if not manifest_file.exists():
        err_console.print(f"[red]Error:[/red] manifest file not found: {manifest_file}")
        err_console.print("Run [bold]opencomplai init[/bold] first.")
        sys.exit(2)
    try:
        manifest = SystemManifest.model_validate(json.loads(manifest_file.read_text()))
    except Exception as e:
        err_console.print(f"[red]Validation error:[/red] {e}")
        sys.exit(2)

    artifact = None
    if artifact_file is not None and artifact_file.exists():
        artifact = ScanStatusArtifact.model_validate(json.loads(artifact_file.read_text()))

    gap_report = None
    if gap_report_file is not None:
        if not gap_report_file.exists():
            err_console.print(f"[red]Error:[/red] gap report not found: {gap_report_file}")
            sys.exit(2)
        gap_report = GapReport.model_validate(json.loads(gap_report_file.read_text()))

    assessment_input = AssessmentInput(
        model=ModelMetadata(
            name=manifest.system_id,
            version=manifest.commit_ref,
            modality="text",
            use_case=manifest.intended_purpose,
            deployment_context="local",
        )
    )
    risk_result = assess(assessment_input)

    fmt = "pdf" if output_file.suffix.lower() == ".pdf" else "html"
    rendered = render_report(
        manifest,
        artifact=artifact,
        gap_report=gap_report,
        risk_result=risk_result,
        fmt=fmt,
    )

    if isinstance(rendered, bytes):
        output_file.write_bytes(rendered)
    else:
        output_file.write_text(rendered, encoding="utf-8")

    console.print(f"[bold green]Wrote report to {output_file}[/bold green]")


def _run_pipeline_evals(
    manifest: SystemManifest,
    commit_ref: str,
    sample_set: EvalSampleSet | None,
    api_available: bool,
    *,
    quiet: bool = False,
) -> tuple[EvalSummary | None, list[str], list[str]]:
    """Returns (eval_summary, extra_failed_controls, extra_evidence_hashes)."""
    if sample_set is None:
        if api_available is False and not quiet:
            console.print("[dim]Evals: no eval sample set supplied (skipped)[/dim]")
        return None, [], []

    sample = sample_set.model_copy(update={"commit_ref": commit_ref})
    extra_hashes: list[str] = []

    if api_available:
        try:
            status, data = _call_service(
                "/v1/evals/run",
                {
                    "system_id": manifest.system_id,
                    "commit_ref": commit_ref,
                    "sample_set": sample.model_dump(),
                },
            )
            if status >= 400:
                err_console.print(f"[red]Eval service error:[/red] {data}")
                sys.exit(2)
            from opencomplai_core.models import EvalReport

            report = EvalReport.model_validate(data)
            extra_hashes.extend(data.get("evidence_hashes", []))
        except ConnectionError:
            report = run_evals(manifest.system_id, commit_ref, sample)
            extra_hashes.extend(r.evidence_hash for r in report.results)
    else:
        report = run_evals(manifest.system_id, commit_ref, sample)
        extra_hashes.extend(r.evidence_hash for r in report.results)

    summary = eval_summary_from_report(report)
    failed = [
        r.evaluator_id for r in report.results if r.outcome == EvaluatorOutcome.FAIL
    ]
    return summary, failed, extra_hashes


def _redacted_report_payload(report: CorroborationReport) -> dict:
    """Ledger-safe corroboration payload — locations and hashes only."""
    return {
        "scan_id": report.scan_id,
        "system_id": report.system_id,
        "commit_ref": report.commit_ref,
        "scanner_version": report.scanner_version,
        "declared_purpose": report.declared_purpose,
        "declared_categories": report.declared_categories,
        "detected_categories": report.detected_categories,
        "discrepancies": report.discrepancies,
        "severity": report.severity.value,
        "report_hash": report.report_hash,
        "locations": sorted({loc for ev in report.evidence for loc in ev.locations}),
        "rationale_codes": sorted({ev.rationale_code for ev in report.evidence}),
    }


def _scan_should_fail(
    report: CorroborationReport,
    fail_on: FailOnLevel,
    baseline_categories: list[str] | None,
) -> bool:
    if fail_on == FailOnLevel.none:
        return False
    # Incomplete / hostile-repo conditions fail any non-none fail-on level.
    if report.scan_errors or report.detector_errors:
        return True
    if fail_on == FailOnLevel.critical:
        return report.severity == DiscrepancySeverity.CRITICAL
    if fail_on == FailOnLevel.major:
        return report.severity in (
            DiscrepancySeverity.MAJOR,
            DiscrepancySeverity.CRITICAL,
        )
    if fail_on == FailOnLevel.new_major:
        baseline = set(baseline_categories or [])
        new_gaps = [d for d in report.discrepancies if d not in baseline]
        return bool(new_gaps) and report.severity in (
            DiscrepancySeverity.MAJOR,
            DiscrepancySeverity.CRITICAL,
        )
    return False


class RichScanProgress:
    def __init__(self) -> None:
        self._progress = Progress(
            SpinnerColumn(),
            TimeElapsedColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(bar_width=32),
            TaskProgressColumn(),
            TextColumn("[dim]{task.fields[label]}"),
        )
        self._tasks: dict[str, TaskID] = {}
        self._progress.start()

    def on_phase(self, phase: str, total: int) -> None:
        labels = {
            "inventory": "Inventorying files",
            "extract": "Extracting features",
            "detect": "Running detectors",
            "ai_intent": "Annotating callsites",
        }
        desc = labels.get(phase, phase)
        if phase not in self._tasks:
            self._tasks[phase] = self._progress.add_task(
                desc, total=total or None, label=""
            )
        else:
            self._progress.update(self._tasks[phase], total=total or None)

    def on_step(self, phase: str, current: int, label: str = "") -> None:
        if phase in self._tasks:
            self._progress.update(self._tasks[phase], completed=current, label=label)

    def on_done(
        self,
        elapsed_s: float,
        file_count: int,
        skip_reasons: dict[str, int] | None = None,
        limits_hit: list[str] | None = None,
    ) -> None:
        self._progress.stop()
        reasons = skip_reasons or {}
        ignored = reasons.get("ignored", 0)
        over_limit = reasons.get("oversized", 0)
        skip_part = ""
        if ignored or over_limit:
            skip_part = f" ({ignored} ignored, {over_limit} over limit)"
        line = (
            f"[dim]Completed in {elapsed_s:.1f} s  ·  {file_count} files inventoried"
            f"{skip_part}  ·  6 extractors  ·  {len(DETECTOR_REGISTRY)} detectors"
        )
        if limits_hit:
            unique_limits = sorted({h.split(":")[0] for h in limits_hit})
            line += f"  ·  limits: {', '.join(unique_limits)}"
        line += "[/dim]"
        console.print(line)


def _bootstrap_ocignore(
    repo_root: Path,
    *,
    ocignore_path: Path | None,
    bootstrap: bool,
) -> ScanConfig:
    resolved_root = repo_root.resolve()
    if bootstrap:
        if not resolved_root.exists():
            console.print(
                "[yellow]Warning:[/yellow] repo-root does not exist — "
                "cannot create .ocignore. Check --repo-root path."
            )
        elif not resolved_root.is_dir():
            console.print(
                "[yellow]Warning:[/yellow] repo-root is not a directory — "
                "cannot create .ocignore."
            )
        else:
            created, path = ensure_ocignore(resolved_root, ocignore_path=ocignore_path)
            if created:
                console.print(
                    f"[dim]Created scan config at {path} (edit patterns and limits as needed)[/dim]"
                )
            elif not path.exists():
                console.print(
                    "[yellow]Warning:[/yellow] could not create .ocignore — "
                    "scanning with empty exclusions and unlimited limits."
                )
    return ScanConfig(ocignore_path=ocignore_path)


def _run_scan_corroboration(
    manifest: SystemManifest,
    commit_ref: str,
    repo_root: Path,
    *,
    emit_evidence: bool = False,
    baseline_categories: list[str] | None = None,
    baseline_ref: str | None = None,
    progress_cb: ScanProgressCallback | None = None,
    scan_config: ScanConfig | None = None,
    ai_intent: bool = False,
    ai_model: str | None = None,
    ai_deep: bool = False,
    ai_legacy: bool = False,
) -> tuple[ScanSummary, CorroborationReport, list[str]]:
    """Returns (scan_summary, full_report, extra_evidence_hashes)."""
    report = run_scan(
        system_id=manifest.system_id,
        commit_ref=commit_ref,
        repo_root=repo_root.resolve(),
        declared_purpose=manifest.intended_purpose,
        config=scan_config or ScanConfig(),
        baseline_ref=baseline_ref,
        baseline_categories=baseline_categories,
        progress_cb=progress_cb,
        ai_intent=ai_intent,
        ai_model=ai_model,
        ai_deep=ai_deep,
        ai_legacy=ai_legacy,
    )
    summary = scan_summary_from_report(report)
    extra_hashes: list[str] = [report.report_hash, *summary.evidence_hashes]
    if emit_evidence:
        evt_id = _emit_event("code_corroboration", _redacted_report_payload(report))
        if evt_id:
            extra_hashes.append(evt_id)
    return summary, report, extra_hashes


def _read_snippet(location: str) -> str | None:
    if ":" not in location:
        return None
    file_path, _, line_str = location.rpartition(":")
    try:
        line_number = int(line_str)
    except ValueError:
        return None
    try:
        lines = (
            Path(file_path).read_text(encoding="utf-8", errors="replace").splitlines()
        )
        if line_number < 1 or line_number > len(lines):
            return None
        return lines[line_number - 1][:80].strip()
    except OSError:
        return None


def _render_scan_md(report: CorroborationReport) -> str:
    lines = [
        f"# Code Corroboration Scan — {report.scan_id}",
        "",
        f"**Timestamp:** {report.generated_at}",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Severity | {report.severity.value} |",
        f"| Declared categories | {', '.join(report.declared_categories) or '(none)'} |",
        f"| Detected categories | {', '.join(report.detected_categories) or '(none)'} |",
        f"| Discrepancy count | {len(report.discrepancies)} |",
        "",
    ]
    if report.discrepancies:
        lines.append("## Discrepancies")
        lines.append("")
        for d in report.discrepancies:
            lines.append(f"- {d}")
        lines.append("")
    lines.extend(
        [
            "## Evidence",
            "",
            "| Location | Token | Category | Confidence | Scope |",
            "|----------|-------|----------|------------|-------|",
        ]
    )
    for ev in report.evidence:
        loc = ev.locations[0] if ev.locations else "(none)"
        lines.append(
            f"| {loc} | {ev.token_label} | {ev.category.value} | "
            f"{ev.confidence:.2f} | {ev.scope.value} |"
        )
    lines.append("")
    return "\n".join(lines)


_INTENT_AREA_LABELS: dict[int | None, str] = {
    None: "unresolved",
    1: "1 Biometrics",
    2: "2 Critical infrastructure",
    3: "3 Education",
    4: "4 Employment",
    5: "5 Essential services",
    6: "6 Law enforcement",
    7: "7 Migration",
    8: "8 Justice & democracy",
}

_INTENT_TIER_ORDER = {
    "prohibited": 0,
    "autonomous_high_risk": 1,
    "advisory_high_risk": 2,
    "high_risk": 3,
    "other": 4,
}

_INTENT_DETAIL_LIMIT = 10


def _render_eu_ai_scan(report: CorroborationReport, *, verbose: bool = False) -> None:
    """Print EU AI Act workflow output from structured eu_ai_scan summary."""
    from collections import Counter, defaultdict

    summary = report.eu_ai_scan
    console.print("\n[bold]EU AI Act Scan[/bold]")
    console.print("  " + "─" * 40)

    if summary is None:
        console.print("  [dim]No AI usage sites detected after gating.[/dim]")
        return

    by_type: dict[str, set[str]] = defaultdict(set)
    by_type_tokens: dict[str, set[str]] = defaultdict(set)
    for cap in summary.capabilities:
        by_type[cap.usage_type].add(cap.file)
        by_type_tokens[cap.usage_type].add(cap.function)

    console.print(
        f"\n  [bold]1. AI usage map[/bold] "
        f"({summary.gated_callsite_count} sites in "
        f"{len({c.file for c in summary.capabilities})} files)"
    )
    for usage_type in sorted(by_type.keys()):
        files = by_type[usage_type]
        tokens = ", ".join(sorted(by_type_tokens[usage_type])[:5])
        console.print(f"     {usage_type:18} {len(files):>3} files   {tokens}")

    if verbose and summary.capabilities:
        console.print("\n  [dim]Detailed AI callsites:[/dim]")
        for cap in summary.capabilities[:50]:
            console.print(
                f"     [cyan]{cap.location}[/cyan]  {cap.function}  ({cap.usage_type})"
            )
        if len(summary.capabilities) > 50:
            console.print(
                f"     [dim]... and {len(summary.capabilities) - 50} more[/dim]"
            )

    console.print(
        f"\n  [bold]2. Prohibited (Art. 5)[/bold] — {len(summary.prohibited)} findings"
    )
    for f in summary.prohibited[: 10 if not verbose else None]:
        console.print(f"     [red]{f.location}[/red]  {f.function}")
        if f.eu_obligation:
            console.print(f"       [yellow]{' | '.join(f.eu_obligation[:2])}[/yellow]")

    console.print(
        f"\n  [bold]3. High-risk (Annex III)[/bold] — {len(summary.high_risk)} findings"
    )
    area_groups: Counter[int | None] = Counter()
    for f in summary.high_risk:
        area_groups[f.annex_iii_area] += 1
    for area, count in sorted(area_groups.items(), key=lambda x: x[0] or 99):
        label = _INTENT_AREA_LABELS.get(area, "unresolved")
        console.print(f"     {label:28} {count:>3}")
    for f in summary.high_risk[: 10 if not verbose else None]:
        label = _INTENT_AREA_LABELS.get(f.annex_iii_area, "unresolved")
        console.print(
            f"     [cyan]{f.location}[/cyan]  {f.function}  [dim]{label}[/dim]"
        )
        if f.eu_obligation:
            console.print(f"       [yellow]{' | '.join(f.eu_obligation[:3])}[/yellow]")

    console.print(
        f"\n  [bold]4. Limited-risk (Art. 50)[/bold] — {len(summary.limited_risk)} findings"
    )
    for f in summary.limited_risk[: 10 if not verbose else None]:
        console.print(f"     [cyan]{f.location}[/cyan]  {f.function}")
        if f.eu_obligation:
            console.print(f"       [yellow]{f.eu_obligation[0]}[/yellow]")

    console.print("\n  [bold]5. Declaration cross-check[/bold]")
    console.print(
        f"     declared:      {', '.join(report.declared_categories) or '(none)'}"
    )
    console.print(
        f"     detected:        {', '.join(report.detected_categories) or '(none)'}"
    )
    if report.discrepancies:
        console.print(f"     discrepancies: {', '.join(report.discrepancies)}")
    else:
        console.print("     discrepancies: (none)")

    all_regulatory = [
        *summary.prohibited,
        *summary.high_risk,
        *summary.limited_risk,
    ]
    with_rationale = [f for f in all_regulatory if f.rationale is not None]
    console.print(
        f"\n  [bold]6. Flag rationale[/bold] — {len(with_rationale)} flagged lines"
    )
    if not with_rationale:
        console.print("     [dim](no regulatory-tier findings to explain)[/dim]")
    else:
        display = with_rationale if verbose else with_rationale[:_INTENT_DETAIL_LIMIT]
        for f in display:
            console.print(f"     [cyan]{f.location}[/cyan]  [dim]{f.function}[/dim]")
            if f.rationale:
                console.print(f"       [bold]WHY:[/bold] {f.rationale.summary}")
                action = f.needed_action or (
                    f.rationale.needed_action if f.rationale else None
                )
                if action:
                    console.print(f"       [bold]ACTION:[/bold] {action}")
                if verbose:
                    if f.rationale.matched_signals:
                        console.print(
                            f"       [dim]signals:[/dim] {', '.join(f.rationale.matched_signals)}"
                        )
                    if f.rationale.regulation_ref:
                        console.print(
                            f"       [dim]regulation:[/dim] {f.rationale.regulation_ref}"
                        )
                    if f.rationale.gate_reason:
                        console.print(
                            f"       [dim]gate:[/dim] {f.rationale.gate_reason}"
                        )
        hidden = len(with_rationale) - len(display)
        if hidden > 0:
            console.print(
                f"\n     [dim]... and {hidden} more (use --ai-verbose to show all)[/dim]"
            )


def _intent_risk_tier(ann) -> str:
    if getattr(ann, "art5_prohibited", False):
        return "prohibited"
    if ann.decision_autonomy == "autonomous" and ann.consequential in (
        "yes",
        "unknown",
    ):
        return "autonomous_high_risk"
    if (
        ann.decision_autonomy in ("advisory", "human_in_loop")
        and ann.annex_iii_area is not None
    ):
        return "advisory_high_risk"
    if ann.annex_iii_area is not None:
        return "high_risk"
    return "other"


def _intent_sort_key(ev) -> tuple:
    ann = ev.intent_annotation
    tier = _intent_risk_tier(ann)
    area = ann.annex_iii_area if ann.annex_iii_area is not None else 99
    return (_INTENT_TIER_ORDER.get(tier, 5), area, -(ann.confidence or 0.0))


def _render_intent_analysis(intent_items: list, *, verbose: bool = False) -> None:
    """Print grouped Annex III summary and ranked intent detail rows."""
    from collections import Counter

    console.print("\n[bold]AI Intent Analysis[/bold]")
    console.print("  " + "─" * 40)

    groups: Counter[tuple[str, str]] = Counter()
    for ev in intent_items:
        ann = ev.intent_annotation
        area_label = _INTENT_AREA_LABELS.get(ann.annex_iii_area, "unresolved")
        tier = _intent_risk_tier(ann)
        groups[(area_label, tier)] += 1

    console.print("  [bold]Summary by Annex III area / risk tier[/bold]")
    summary_rows = sorted(
        groups.items(),
        key=lambda item: (
            _INTENT_TIER_ORDER.get(item[0][1], 5),
            item[0][0],
        ),
    )
    for (area_label, tier), count in summary_rows:
        console.print(f"    {area_label:28} {tier:22} {count:>3}")

    sorted_items = sorted(intent_items, key=_intent_sort_key)
    display_items = sorted_items if verbose else sorted_items[:_INTENT_DETAIL_LIMIT]
    hidden = len(sorted_items) - len(display_items)

    console.print("\n  [bold]Callsite details[/bold]")
    for ev in display_items:
        ann = ev.intent_annotation
        loc = ev.locations[0] if ev.locations else ""
        area_label = _INTENT_AREA_LABELS.get(ann.annex_iii_area, "unresolved")
        tier = _intent_risk_tier(ann)
        console.print(
            f"  [cyan]{loc}[/cyan]  [dim]{ev.token_label}[/dim]  "
            f"[dim]area:[/dim] {area_label}  [dim]tier:[/dim] {tier}"
        )
        console.print(f"    decision_autonomy : {ann.decision_autonomy}")
        console.print(f"    subject_type      : {ann.subject_type}")
        console.print(f"    consequential     : {ann.consequential}")
        if ann.eu_obligation:
            obligation_str = " | ".join(ann.eu_obligation[:3])
            console.print(f"    eu_obligation     : [yellow]{obligation_str}[/yellow]")
        if ann.explanation:
            console.print(
                f"    explanation       : [italic dim]{ann.explanation}[/italic dim]"
            )
        if ann.needed_action:
            console.print(f"    needed_action     : [green]{ann.needed_action}[/green]")
        console.print(f"    confidence        : {ann.confidence:.2f}")

    if hidden > 0:
        console.print(
            f"\n  [dim]... and {hidden} more (use --ai-verbose to show all)[/dim]"
        )


def _print_scan_human(
    report: CorroborationReport,
    *,
    ai_intent: bool = False,
    ai_verbose: bool = False,
    ai_legacy: bool = False,
) -> None:
    console.print("\n[bold]Code Corroboration Scan[/bold]")
    console.print(f"  severity:     {report.severity.value}")
    console.print(
        f"  declared:     {', '.join(report.declared_categories) or '(none)'}"
    )
    console.print(
        f"  detected:     {', '.join(report.detected_categories) or '(none)'}"
    )
    if report.discrepancies:
        console.print(f"  discrepancies: {', '.join(report.discrepancies)}")
    else:
        console.print("  discrepancies: (none)")

    empty_inventory = next(
        (w for w in report.warnings if w.startswith("empty_inventory:")),
        None,
    )
    if empty_inventory:
        console.print(
            f"\n  [yellow]Warning:[/yellow] {empty_inventory.split(':', 1)[1].strip()}"
        )

    if not ai_intent or ai_legacy:
        if report.evidence:
            console.print("  evidence:")
            for ev in report.evidence[:8]:
                for loc in ev.locations[:3]:
                    console.print(
                        f"    - {loc}  "
                        f'[dim]token:[/dim] "{ev.token_label}"  '
                        f"[dim]category:[/dim] {ev.category.value}  "
                        f"[dim]confidence:[/dim] {ev.confidence:.2f}"
                    )
                    snippet = _read_snippet(loc)
                    if snippet:
                        console.print(f"      [italic dim]{snippet}[/italic dim]")
        else:
            console.print(
                "  [dim]No local AI signals detected — not a compliance verdict.[/dim]"
            )

    if ai_intent:
        if ai_legacy:
            intent_items = [
                ev for ev in report.evidence if ev.intent_annotation is not None
            ]
            if intent_items:
                _render_intent_analysis(intent_items, verbose=ai_verbose)
            else:
                console.print(
                    "\n[dim]AI Intent Analysis: no callsites annotated (plugin ran but found no signals).[/dim]"
                )
        else:
            _render_eu_ai_scan(report, verbose=ai_verbose)

    console.print(
        "\n  [dim]Declaration is authoritative; confirm or update intended_purpose.[/dim]"
    )


@app.command("scan")
def scan_cmd(
    manifest_file: Path = typer.Option(
        Path("system-manifest.json"), "--manifest", "-m"
    ),
    repo_root: Path = typer.Option(Path("."), "--repo-root"),
    commit_ref: str = typer.Option("HEAD", "--commit-ref"),
    emit_evidence: bool = typer.Option(True, "--emit-evidence/--no-emit-evidence"),
    enqueue_review: bool = typer.Option(False, "--enqueue-review/--no-enqueue-review"),
    baseline: Path | None = typer.Option(
        None, "--baseline", help="JSON file with accepted discrepancy categories"
    ),
    fail_on: FailOnLevel = typer.Option(
        FailOnLevel.none, "--fail-on", help="Opt-in CI gating (default: none)"
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
    output_file: Path | None = typer.Option(
        None, "--output-file", "-f", help="Write scan results to file (.json or .md)"
    ),
    sarif_output: Path | None = typer.Option(
        None,
        "--sarif-output",
        help="Write scan evidence as SARIF 2.1.0 (for GitHub code scanning / GHAS upload)",
    ),
    ocignore_path: Path | None = typer.Option(
        None, "--ocignore", help="Path to .ocignore (must be inside --repo-root)"
    ),
    ocignore_bootstrap: bool = typer.Option(
        True,
        "--ocignore-bootstrap/--no-ocignore-bootstrap",
        help="Create default .ocignore on first scan if missing",
    ),
    ai_intent: bool = typer.Option(
        False,
        "--ai-intent",
        help="Enable AI intent classification (requires opencomplai-ai)",
    ),
    ai_model: str | None = typer.Option(
        None,
        "--ai-model",
        help="AI model to use (overrides ~/.opencomplai/ai-config.yaml)",
    ),
    ai_deep: bool = typer.Option(
        False,
        "--ai-deep",
        help=(
            "Run AI intent analysis on every callsite in the repo. "
            "By default only callsites from files with lexical findings are annotated (faster)."
        ),
    ),
    ai_verbose: bool = typer.Option(
        False,
        "--ai-verbose",
        help="Show all AI intent callsite annotations (default: top 10 by risk tier).",
    ),
    ai_legacy: bool = typer.Option(
        False,
        "--ai-legacy",
        help=(
            "Restore pre-v2 behavior: ungated lexical evidence and Art.50 default "
            "for non-regulatory callsites."
        ),
    ),
    framework_detectors: bool = typer.Option(
        False,
        "--framework-detectors",
        help=(
            "Opt-in: AST-level framework-object detection (LangChain AgentExecutor, "
            "CrewAI Crew, AutoGen ConversableAgent, LangGraph StateGraph, etc.) — "
            "informational only, in addition to the existing lexical orchestration signal."
        ),
    ),
    quick: bool = typer.Option(
        False,
        "--quick",
        help=(
            "Zero-config discovery scan: skip manifest loading, never gate CI, never "
            "emit ledger events. Prints detected categories and a suggested `init` command."
        ),
    ),
) -> None:
    """Cross-check declared purpose against AI capability signals in the repo."""
    if quick:
        fail_on = FailOnLevel.none
        emit_evidence = False
        enqueue_review = False
        manifest = SystemManifest(
            system_id="quick-scan",
            intended_purpose="",
            compliance_target="EU_AI_ACT",
            high_risk_presumption=False,
            commit_ref=commit_ref,
        )
    elif not manifest_file.exists():
        err_console.print(f"[red]Error:[/red] manifest not found: {manifest_file}")
        sys.exit(2)
    else:
        manifest = SystemManifest.model_validate(json.loads(manifest_file.read_text()))
    baseline_categories: list[str] | None = None
    baseline_ref: str | None = None
    if baseline is not None:
        if not baseline.exists():
            err_console.print(f"[red]Error:[/red] baseline not found: {baseline}")
            sys.exit(2)
        baseline_data = json.loads(baseline.read_text())
        baseline_categories = baseline_data.get("accepted_categories", [])
        baseline_ref = baseline_data.get("baseline_ref")

    if ai_intent:
        ai_intent = _preload_ai_model(ai_model)

    requested_repo_root = repo_root
    try:
        from opencomplai_core.scan_engine import validate_scan_repo_root

        repo_root = validate_scan_repo_root(repo_root, auto_correct=True)
    except FileNotFoundError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        err_console.print(
            "[dim]Tip: use the website project's own system-manifest.json when scanning "
            "a different repo.[/dim]"
        )
        sys.exit(2)
    except NotADirectoryError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        sys.exit(2)

    if not requested_repo_root.exists() and repo_root.exists():
        err_console.print(
            f"[yellow]Note:[/yellow] auto-corrected --repo-root "
            f"{requested_repo_root} → {repo_root}"
        )
        website_manifest = repo_root / "system-manifest.json"
        if (
            manifest_file.resolve() != website_manifest.resolve()
            and website_manifest.is_file()
        ):
            err_console.print(
                f"[dim]Tip: consider --manifest {website_manifest} for this repo.[/dim]"
            )

    progress_cb: ScanProgressCallback | None = None
    if output == OutputFormat.human and sys.stdout.isatty():
        progress_cb = RichScanProgress()

    scan_config = _bootstrap_ocignore(
        repo_root,
        ocignore_path=ocignore_path,
        bootstrap=ocignore_bootstrap,
    )

    from opencomplai_core.project_config import find_project_config, load_project_config

    project_config_path = find_project_config(repo_root)
    resolved_fail_on = fail_on
    resolved_framework_detectors = framework_detectors
    if project_config_path is not None:
        project_config = load_project_config(project_config_path)
        # Config values only apply where the CLI flag is still at its built-in default —
        # an explicit CLI flag always wins over opencomplai.yaml (never the reverse).
        if fail_on == FailOnLevel.none and project_config.scan_fail_on is not None:
            resolved_fail_on = FailOnLevel(project_config.scan_fail_on)
        if (
            framework_detectors is False
            and project_config.scan_framework_detectors is not None
        ):
            resolved_framework_detectors = project_config.scan_framework_detectors
        console.print(f"[dim]Loaded project config: {project_config_path}[/dim]")
    fail_on = resolved_fail_on
    framework_detectors = resolved_framework_detectors

    scan_config.framework_detectors = framework_detectors

    _summary, report, _ = _run_scan_corroboration(
        manifest,
        commit_ref,
        repo_root,
        emit_evidence=emit_evidence,
        baseline_categories=baseline_categories,
        baseline_ref=baseline_ref,
        progress_cb=progress_cb,
        scan_config=scan_config,
        ai_intent=ai_intent,
        ai_model=ai_model,
        ai_deep=ai_deep,
        ai_legacy=ai_legacy,
    )

    if output == OutputFormat.json:
        envelope = wrap_scan_output(
            json.loads(report.model_dump_json()),
            scan_errors=list(report.scan_errors) + list(report.detector_errors),
            tool_version=__version__,
        )
        console.print_json(envelope.model_dump_json(indent=2))
    else:
        _print_scan_human(
            report,
            ai_intent=ai_intent,
            ai_verbose=ai_verbose,
            ai_legacy=ai_legacy,
        )

    if quick:
        categories = ", ".join(report.detected_categories) or "(none)"
        console.print(
            "\n[bold]Discovery only — not a compliance verdict.[/bold] "
            "No manifest was loaded and no CI gate was evaluated.\n"
        )
        console.print(f"[dim]Detected categories:[/dim] {categories}")
        if report.detected_categories:
            purpose_guess = ", ".join(report.detected_categories)
            console.print(
                "\n[bold]Suggested next step:[/bold]\n"
                f'  opencomplai init --system-id <your-system-id> --intended-purpose "{purpose_guess}"\n'
            )
        else:
            console.print(
                "\n[dim]No AI signals detected in this repo — "
                "`opencomplai init` when you have a system to declare.[/dim]\n"
            )
        sys.exit(0)

    if output_file is not None:
        suffix = output_file.suffix.lower()
        if suffix == ".json":
            output_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        elif suffix == ".md":
            output_file.write_text(_render_scan_md(report), encoding="utf-8")
        else:
            console.print(
                f"[yellow]Unknown file extension '{suffix}'; writing JSON.[/yellow]"
            )
            output_file.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"[dim]Results written to {output_file}[/dim]")

    if sarif_output is not None:
        from opencomplai_core.scanner.sarif import report_to_sarif

        sarif_output.write_text(json.dumps(report_to_sarif(report), indent=2), encoding="utf-8")
        console.print(f"[dim]SARIF written to {sarif_output}[/dim]")

    if enqueue_review and report.severity in (
        DiscrepancySeverity.MAJOR,
        DiscrepancySeverity.CRITICAL,
    ):
        try:
            _call_service(
                "/v1/reviews/enqueue",
                {
                    "system_id": manifest.system_id,
                    "commit_ref": commit_ref,
                    "reason": "manifest_discrepancy",
                    "payload_ref": report.report_hash,
                    "context": {
                        "discrepancies": report.discrepancies,
                        "severity": report.severity.value,
                        "locations": sorted(
                            {loc for ev in report.evidence for loc in ev.locations}
                        )[:20],
                    },
                },
            )
        except Exception:
            pass

    if _scan_should_fail(report, fail_on, baseline_categories):
        sys.exit(1)
    sys.exit(0)


@app.command("check")
def check_cmd(
    manifest_file: Path = typer.Option(
        Path("system-manifest.json"),
        "--manifest",
        "-m",
        help="Path to system manifest JSON file",
    ),
    commit_ref: str = typer.Option("HEAD", "--commit-ref", help="Git commit reference"),
    scan_mode: str = typer.Option("local", "--scan-mode", help="ci | local | airgap"),
    sample_set_file: Path | None = typer.Option(
        None,
        "--sample-set",
        help="Path to EvalSampleSet JSON for safety/bias/leakage evaluators",
    ),
    sign: bool = typer.Option(
        False,
        "--sign/--no-sign",
        help="Sign the status artifact (requires signing key)",
    ),
    run_code_scan: bool = typer.Option(
        False, "--scan", help="Run code corroboration scan (opt-in)"
    ),
    repo_root: Path = typer.Option(Path("."), "--repo-root"),
    emit_scan_evidence: bool = typer.Option(True, "--emit-evidence/--no-emit-evidence"),
    scan_fail_on: FailOnLevel = typer.Option(
        FailOnLevel.none, "--fail-on", help="Gate check on scan discrepancies"
    ),
    scan_baseline: Path | None = typer.Option(None, "--baseline"),
    with_gaps: bool = typer.Option(
        False,
        "--with-gaps",
        help="Attach a per-article gap_report to the artifact (additive, informational only)",
    ),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """
    Run a full compliance check against EU AI Act rules (PRD §12.4).

    Produces a signed ScanStatusArtifact appended to the evidence ledger.
    When OPENCOMPLAI_API_URL is set, orchestrates all services; otherwise
    uses the local engine with local artifact output.
    """
    if not manifest_file.exists():
        err_console.print(f"[red]Error:[/red] manifest file not found: {manifest_file}")
        err_console.print("Run [bold]opencomplai init[/bold] first.")
        sys.exit(2)

    try:
        raw = json.loads(manifest_file.read_text())
        manifest = SystemManifest.model_validate(raw)
    except Exception as e:
        err_console.print(f"[red]Manifest validation error:[/red] {e}")
        sys.exit(2)

    if manifest.checker_session is None:
        err_console.print(
            "[yellow]WARN:[/yellow] No checker session in manifest. Run "
            "[bold]opencomplai checker[/bold] or [bold]opencomplai init --interactive[/bold] "
            "for EU AI Act applicability guidance."
        )
    elif output == OutputFormat.human:
        cs = manifest.checker_session
        role = manifest.operator_role or "unknown"
        console.print(
            f"[dim]Applicability checker:[/dim] session {cs.session_id[:8]}… "
            f"(v{cs.checker_version}, role={role})"
        )

    install_id = _get_install_id()
    time.monotonic()

    api_available = bool(os.environ.get("OPENCOMPLAI_API_URL", "").strip())
    sample_set = _load_sample_set(sample_set_file, manifest)
    eval_summary, eval_failed, eval_hashes = _run_pipeline_evals(
        manifest,
        commit_ref,
        sample_set,
        api_available,
        quiet=(output == OutputFormat.json),
    )

    scan_summary: ScanSummary | None = None
    scan_report: CorroborationReport | None = None
    scan_failed = False
    baseline_categories: list[str] | None = None
    if scan_baseline is not None and scan_baseline.exists():
        baseline_data = json.loads(scan_baseline.read_text())
        baseline_categories = baseline_data.get("accepted_categories", [])

    if run_code_scan:
        scan_config = _bootstrap_ocignore(repo_root, ocignore_path=None, bootstrap=True)
        _, scan_report, scan_hashes = _run_scan_corroboration(
            manifest,
            commit_ref,
            repo_root,
            emit_evidence=emit_scan_evidence,
            baseline_categories=baseline_categories,
            scan_config=scan_config,
        )
        scan_summary = scan_summary_from_report(scan_report)
        eval_hashes = list(dict.fromkeys((eval_hashes or []) + scan_hashes))
        scan_failed = _scan_should_fail(scan_report, scan_fail_on, baseline_categories)

    if api_available:
        artifact = _run_service_check(
            manifest,
            commit_ref,
            scan_mode,
            install_id,
            sign,
            eval_summary,
            eval_failed,
            eval_hashes,
            scan_summary=scan_summary,
        )
    else:
        artifact = _run_local_check(
            manifest,
            commit_ref,
            scan_mode,
            install_id,
            sign,
            eval_summary,
            eval_failed,
            eval_hashes,
            scan_summary=scan_summary,
        )

    if scan_failed and artifact.result == ScanResult.PASS:
        artifact = artifact.model_copy(update={"result": ScanResult.CONTROL_FAIL})
        artifact.failed_controls = list(
            dict.fromkeys([*artifact.failed_controls, "CODE_CORROBORATION_GAP"])
        )

    if with_gaps:
        gap_assessment_input = AssessmentInput(
            model=ModelMetadata(
                name=manifest.system_id,
                version=commit_ref,
                modality="text",
                use_case=manifest.intended_purpose,
                deployment_context=scan_mode,
            )
        )
        gap_risk_result = assess(gap_assessment_input)
        gap_eval_report = None
        if sample_set is not None:
            gap_eval_report = run_evals(
                manifest.system_id, commit_ref, sample_set.model_copy(update={"commit_ref": commit_ref})
            )
        gap_report = build_gap_report(
            system_id=manifest.system_id,
            commit_ref=commit_ref,
            risk_result=gap_risk_result,
            corroboration_report=scan_report,
            eval_report=gap_eval_report,
        )
        artifact = artifact.model_copy(update={"gap_report": gap_report})

    # Write artifact to disk for CI consumption
    artifact_path = Path("compliance-artifact.json")
    artifact_path.write_text(artifact.model_dump_json(indent=2))

    if output == OutputFormat.json:
        console.print_json(artifact.model_dump_json(indent=2))
    else:
        _print_artifact_human(artifact)

    sys.exit(_exit_code(artifact.result, scan_mode))


def _run_service_check(
    manifest: SystemManifest,
    commit_ref: str,
    scan_mode: str,
    install_id: str,
    sign: bool,
    eval_summary: EvalSummary | None = None,
    eval_failed: list[str] | None = None,
    eval_hashes: list[str] | None = None,
    scan_summary: ScanSummary | None = None,
) -> ScanStatusArtifact:
    """Full 10-step orchestration via gateway services (PRD §12.4)."""
    start_ms = time.monotonic()
    evidence_hashes: list[str] = []
    pending_verifications_count = 0

    # Step 1 — emit compliance_check_started
    evt_id = _emit_event(
        "compliance_check_started",
        {
            "install_id": install_id,
            "system_id": manifest.system_id,
            "commit_ref": commit_ref,
            "scan_mode": scan_mode,
        },
    )
    if evt_id:
        evidence_hashes.append(evt_id)

    # Step 2 — validate manifest
    try:
        status, _val_data = _call_service(
            "/v1/manifests/validate",
            {
                "system_id": manifest.system_id,
                "intended_purpose": manifest.intended_purpose,
                "compliance_target": manifest.compliance_target,
                "high_risk_presumption": manifest.high_risk_presumption,
                "commit_ref": commit_ref,
            },
        )
        if status >= 400:
            return _finalize_artifact(
                install_id,
                manifest.system_id,
                commit_ref,
                scan_mode,
                ScanResult.VALIDATION_FAIL,
                ["MANIFEST_INVALID"],
                [],
                "sha256:validation_failed",
                0,
                int((time.monotonic() - start_ms) * 1000),
                sign,
            )
    except ConnectionError as exc:
        err_console.print(f"[red]Service error:[/red] {exc}")
        sys.exit(3)

    # Step 3 — classify risk
    try:
        status, risk_data = _call_service(
            "/v1/risk/classify",
            {
                "system_id": manifest.system_id,
                "intended_purpose": manifest.intended_purpose,
            },
        )
        if status >= 400:
            return _finalize_artifact(
                install_id,
                manifest.system_id,
                commit_ref,
                scan_mode,
                ScanResult.VALIDATION_FAIL,
                [],
                evidence_hashes,
                "sha256:classify_failed",
                0,
                int((time.monotonic() - start_ms) * 1000),
                sign,
            )
    except ConnectionError as exc:
        err_console.print(f"[red]Service error:[/red] {exc}")
        sys.exit(3)

    trap_detected = risk_data.get("trap_detected", False)
    profiling_detected = risk_data.get("profiling_detected", False)
    risk_class = risk_data.get("risk_class", "minimal")
    rationale_hash = risk_data.get("rationale_hash", "sha256:unknown")
    evidence_event_id = risk_data.get("evidence_event_id", "")
    if evidence_event_id:
        evidence_hashes.append(evidence_event_id)

    # Step 4 — trap gate
    if trap_detected:
        trap_evt = _emit_event(
            "trap_detected",
            {
                "system_id": manifest.system_id,
                "commit_ref": commit_ref,
                "reason_code": "SUBSTANTIAL_MODIFICATION",
                "risk_class": risk_class,
            },
        )
        if trap_evt:
            evidence_hashes.append(trap_evt)
        return _finalize_artifact(
            install_id,
            manifest.system_id,
            commit_ref,
            scan_mode,
            ScanResult.TRAP_DETECTED,
            _controls_from_risk(risk_class, trap_detected, profiling_detected),
            evidence_hashes,
            rationale_hash,
            0,
            int((time.monotonic() - start_ms) * 1000),
            sign,
        )

    # Step 5 — derive failed controls
    failed_controls = _controls_from_risk(risk_class, trap_detected, profiling_detected)
    if eval_failed:
        failed_controls = list(dict.fromkeys(failed_controls + eval_failed))
    if eval_hashes:
        evidence_hashes.extend(eval_hashes)

    # Step 6 — verify claims
    try:
        status, verify_data = _call_service(
            "/v1/verify/claims",
            {
                "system_id": manifest.system_id,
                "claim_ref": f"{manifest.system_id}:manifest",
                "source_ref": "offline://manifest",
                "expected_value": manifest.intended_purpose,
            },
        )
        outcome = verify_data.get("outcome", "pending")
        if outcome == "pending":
            pending_verifications_count += 1
        task_id = verify_data.get("task_id", "")
        if task_id:
            evidence_hashes.append(task_id)
    except Exception:
        pending_verifications_count += 1

    # Step 7 — generate dossier
    dossier_ok = True
    try:
        status, doc_data = _call_service(
            "/v1/docs/generate",
            {
                "system_id": manifest.system_id,
                "commit_ref": commit_ref,
                "intended_purpose": manifest.intended_purpose,
                "provider_name": "Unknown Provider",
                "high_risk_presumption": manifest.high_risk_presumption,
                "training_data_description": manifest.training_data_description,
                "model_architecture": manifest.model_architecture,
                "performance_metrics": manifest.performance_metrics,
                "known_limitations": manifest.known_limitations,
                "human_oversight_measures": manifest.human_oversight_measures,
                "monitoring_approach": manifest.monitoring_approach,
                "incident_response_procedure": manifest.incident_response_procedure,
            },
        )
        if status >= 400:
            dossier_ok = False
        else:
            bundle_cs = doc_data.get("bundle_checksum", "")
            if bundle_cs:
                evidence_hashes.append(bundle_cs)
    except Exception:
        dossier_ok = False

    duration_ms = int((time.monotonic() - start_ms) * 1000)

    # Determine final result
    if not dossier_ok and pending_verifications_count > 0:
        result = ScanResult.DEGRADED_COMPLETE
    elif failed_controls:
        result = ScanResult.CONTROL_FAIL
    else:
        result = ScanResult.PASS

    artifact = _finalize_artifact(
        install_id,
        manifest.system_id,
        commit_ref,
        scan_mode,
        result,
        failed_controls,
        evidence_hashes,
        rationale_hash,
        pending_verifications_count,
        duration_ms,
        sign,
        eval_summary=eval_summary,
        scan_summary=scan_summary,
    )

    # Steps 9 — emit completion events
    _emit_event(
        "compliance_check_completed",
        {
            "install_id": install_id,
            "system_id": manifest.system_id,
            "status": result.value,
            "duration_ms": duration_ms,
            "failed_controls": failed_controls,
            "pending_verifications_count": pending_verifications_count,
        },
    )
    _emit_event(
        "first_scan_completed",
        {
            "install_id": install_id,
            "system_id": manifest.system_id,
            "result": result.value,
            "duration_ms": duration_ms,
        },
    )

    # Step 8 — append artifact to ledger
    _emit_event(
        "scan_status_artifact",
        json.loads(artifact.model_dump_json()),
    )

    return artifact


def _run_local_check(
    manifest: SystemManifest,
    commit_ref: str,
    scan_mode: str,
    install_id: str,
    sign: bool,
    eval_summary: EvalSummary | None = None,
    eval_failed: list[str] | None = None,
    eval_hashes: list[str] | None = None,
    scan_summary: ScanSummary | None = None,
) -> ScanStatusArtifact:
    """Local engine fallback — no services required."""
    start_ms = time.monotonic()

    assessment_input = AssessmentInput(
        model=ModelMetadata(
            name=manifest.system_id,
            version=commit_ref,
            modality="text",
            use_case=manifest.intended_purpose,
            deployment_context=scan_mode,
        )
    )
    risk_result = assess(assessment_input)
    result, failed_controls = _result_from_local(risk_result)
    if eval_failed:
        failed_controls = list(dict.fromkeys(failed_controls + eval_failed))
        if result == ScanResult.PASS:
            result = ScanResult.CONTROL_FAIL

    import hashlib

    rationale_hash = (
        f"sha256:{hashlib.sha256(risk_result.evidence_summary.encode()).hexdigest()}"
    )
    duration_ms = int((time.monotonic() - start_ms) * 1000)
    evidence_hashes = list(eval_hashes or [])

    return _finalize_artifact(
        install_id,
        manifest.system_id,
        commit_ref,
        scan_mode,
        result,
        failed_controls,
        evidence_hashes,
        rationale_hash,
        0,
        duration_ms,
        sign,
        eval_summary=eval_summary,
        scan_summary=scan_summary,
    )


def _finalize_artifact(
    install_id: str,
    system_id: str,
    commit_ref: str,
    scan_mode: str,
    result: ScanResult,
    failed_controls: list[str],
    evidence_hashes: list[str],
    rationale_hash: str,
    pending_verifications_count: int,
    duration_ms: int,
    sign: bool,
    eval_summary: EvalSummary | None = None,
    scan_summary: ScanSummary | None = None,
) -> ScanStatusArtifact:
    """Build and optionally sign the ScanStatusArtifact."""
    artifact = ScanStatusArtifact(
        install_id=install_id,
        system_id=system_id,
        commit_ref=commit_ref,
        result=result,
        failed_controls=failed_controls,
        evidence_hashes=evidence_hashes,
        rationale_hash=rationale_hash,
        duration_ms=duration_ms,
        pending_verifications_count=pending_verifications_count,
        signature=None,
        eval_summary=eval_summary,
        scan_summary=scan_summary,
    )

    if sign and _SIGNING_KEY.exists():
        try:
            from opencomplai_core.signing import sign_artifact

            artifact.signature = sign_artifact(artifact, _SIGNING_KEY)
        except Exception as exc:
            err_console.print(f"[yellow]Warning: signing failed — {exc}[/yellow]")

    return artifact


def _print_artifact_human(artifact: ScanStatusArtifact) -> None:
    result_color = "green" if artifact.result == ScanResult.PASS else "red"
    console.print("\n[bold]Opencomplai Compliance Check[/bold]")
    console.print(f"  system_id:    {artifact.system_id}")
    console.print(f"  commit_ref:   {artifact.commit_ref}")
    console.print(
        f"  result:       [bold {result_color}]{artifact.result.value.upper()}[/bold {result_color}]"
    )
    console.print(f"  duration_ms:  {artifact.duration_ms}")
    console.print(
        f"  signed:       {'yes' if artifact.signature else 'no (OSS unsigned)'}"
    )
    if artifact.failed_controls:
        console.print(f"  failed_controls: {', '.join(artifact.failed_controls)}")
    if artifact.pending_verifications_count:
        console.print(
            f"  pending_verifications: {artifact.pending_verifications_count}"
        )
    if artifact.eval_summary:
        console.print(
            f"  eval_outcome:      {artifact.eval_summary.overall_outcome.value}"
        )
    if artifact.scan_summary:
        console.print(f"  scan_severity:     {artifact.scan_summary.severity.value}")
        if artifact.scan_summary.discrepancies:
            console.print(
                f"  scan_gaps:         {', '.join(artifact.scan_summary.discrepancies)}"
            )
    console.print("\n  [dim]Artifact written to compliance-artifact.json[/dim]")


@app.command("eval")
def eval_cmd(
    manifest_file: Path = typer.Option(
        Path("system-manifest.json"), "--manifest", "-m"
    ),
    sample_set_file: Path | None = typer.Option(
        None,
        "--sample-set",
        help="Path to EvalSampleSet JSON (required unless --suite is set)",
    ),
    commit_ref: str = typer.Option("HEAD", "--commit-ref"),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help=(
            "Opt-in: call a live model provider (e.g. 'openai') for each prompt in the "
            "sample set. Non-deterministic and network-dependent -- never runs by "
            "default, and never invoked by `opencomplai check`."
        ),
    ),
    provider_model: str | None = typer.Option(
        None, "--model", help="Model name to request from --provider or --suite (e.g. gpt-4o-mini)"
    ),
    provider_api_key_env: str = typer.Option(
        "OPENCOMPLAI_PROVIDER_API_KEY",
        "--provider-api-key-env",
        help="Environment variable holding the provider API key",
    ),
    suite: str | None = typer.Option(
        None,
        "--suite",
        help=(
            "Opt-in: run an external benchmark suite bridge (currently 'compl-ai'). "
            "Requires the 'opencomplai-core[compl-ai-bridge]' extra. Non-deterministic, "
            "network-dependent — never invoked by `opencomplai check`."
        ),
    ),
    tasks: str | None = typer.Option(
        None,
        "--tasks",
        help="Comma-separated curated COMPL-AI tasks (default: strong_reject,bbq,bigbench_calibration)",
    ),
    log_dir: Path | None = typer.Option(
        None,
        "--log-dir",
        help="Local Inspect log directory for --suite compl-ai (no S3 in this release)",
    ),
) -> None:
    """Run safety, bias, and data-leakage pipeline evaluators."""
    if suite is not None:
        if suite != "compl-ai":
            err_console.print(f"[red]Error:[/red] unknown --suite {suite!r} (only 'compl-ai' is supported)")
            sys.exit(2)
        from opencomplai_core.bridges.compl_ai import (
            curated_task_names,
            is_inspect_available,
            run_compl_ai_suite,
        )

        if not is_inspect_available():
            err_console.print(
                "[red]Error:[/red] --suite compl-ai requires the optional 'compl-ai-bridge' extra.\n"
                "  Install with: pip install 'opencomplai-core\\[compl-ai-bridge]'"
            )
            sys.exit(2)
        if not provider_model:
            err_console.print("[red]Error:[/red] --model is required with --suite compl-ai")
            sys.exit(2)
        api_key = os.environ.get(provider_api_key_env, "") or os.environ.get("OPENAI_API_KEY", "")
        task_list = (
            [t.strip() for t in tasks.split(",") if t.strip()]
            if tasks
            else curated_task_names()
        )
        console.print(
            "[bold yellow]COMPL-AI bridge[/bold yellow] — non-deterministic, never gates "
            "`opencomplai check` (gate_on_bridge=false)."
        )
        try:
            suite_results = run_compl_ai_suite(
                task_list,
                model=provider_model,
                api_key=api_key,
                log_dir=log_dir,
            )
        except Exception as exc:  # noqa: BLE001 — surface bridge errors cleanly
            err_console.print(f"[red]Error:[/red] COMPL-AI suite failed: {exc}")
            sys.exit(2)
        if output == OutputFormat.json:
            envelope = wrap_scan_output(
                {
                    "suite": "compl-ai",
                    "model": provider_model,
                    "deterministic": False,
                    "tasks": [r.model_dump() for r in suite_results],
                },
                tool_version=__version__,
            )
            console.print_json(envelope.model_dump_json(indent=2))
        else:
            for r in suite_results:
                console.print(
                    f"  {r.evaluator_id}: {r.outcome.value} score={r.score} "
                    f"(n={r.sample_count})"
                )
        if any(r.outcome == EvaluatorOutcome.FAIL for r in suite_results):
            sys.exit(1)
        sys.exit(0)

    if sample_set_file is None:
        err_console.print("[red]Error:[/red] --sample-set is required unless --suite is set")
        sys.exit(2)
    if not manifest_file.exists():
        err_console.print(f"[red]Error:[/red] manifest not found: {manifest_file}")
        sys.exit(2)
    manifest = SystemManifest.model_validate(json.loads(manifest_file.read_text()))
    sample_set = _load_sample_set(sample_set_file, manifest)
    assert sample_set is not None

    api_available = bool(os.environ.get("OPENCOMPLAI_API_URL", "").strip())
    summary, _failed, _ = _run_pipeline_evals(
        manifest, commit_ref, sample_set, api_available
    )
    assert summary is not None

    if output == OutputFormat.json:
        console.print_json(summary.model_dump_json(indent=2))
    else:
        console.print("[bold]Opencomplai Pipeline Evals[/bold]")
        console.print(f"  overall: {summary.overall_outcome.value}")
        if summary.failed_evaluator_ids:
            console.print(f"  failed:  {', '.join(summary.failed_evaluator_ids)}")
        if summary.skipped_evaluators:
            console.print(f"  skipped: {summary.skipped_evaluators}")

    if provider is not None:
        if not provider_model:
            err_console.print("[red]Error:[/red] --model is required when --provider is set")
            sys.exit(2)
        api_key = os.environ.get(provider_api_key_env, "")
        if not api_key:
            err_console.print(
                f"[red]Error:[/red] {provider_api_key_env} is not set; "
                "cannot call --provider without an API key"
            )
            sys.exit(2)

        from opencomplai_core.model_providers import get_provider_client

        client = get_provider_client(provider)
        completions = [
            client.complete(prompt, model=provider_model, api_key=api_key)
            for prompt in sample_set.prompts
        ]
        provider_payload = {
            "provider": provider,
            "model": provider_model,
            "deterministic": False,
            "note": "Live model-provider call — non-deterministic, network-dependent, opt-in only.",
            "completions": [
                {"prompt": c.prompt, "completion": c.completion} for c in completions
            ],
        }
        if output == OutputFormat.json:
            console.print_json(json.dumps(provider_payload, indent=2))
        else:
            console.print(
                f"\n[bold yellow]Live provider call ({provider}/{provider_model}) "
                "— non-deterministic, not part of the deterministic evaluator suite[/bold yellow]"
            )
            for c in completions:
                console.print(f"  prompt:     {c.prompt[:80]}")
                console.print(f"  completion: {c.completion[:80]}")

    if summary.overall_outcome == EvaluatorOutcome.FAIL:
        sys.exit(1)
    sys.exit(0)


@app.command("serve")
def serve_cmd(
    project_root: Path = typer.Argument(
        Path("."),
        help="Project directory to scan (must stay on this machine)",
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Loopback host only"),
    port: int = typer.Option(8420, "--port", help="Local port"),
) -> None:
    """Start a localhost-only scan dashboard (not Pro / SaaS)."""
    run_serve(project_root, host=host, port=port)


# ---------------------------------------------------------------------------
# risk / docs / sync sub-commands
# ---------------------------------------------------------------------------


@risk_app.command("classify")
def risk_classify_cmd(
    system_id: str = typer.Option(..., "--system-id"),
    intended_purpose: str = typer.Option(..., "--intended-purpose"),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Classify a system's risk level under EU AI Act Annex III."""
    try:
        status, data = _call_service(
            "/v1/risk/classify",
            {"system_id": system_id, "intended_purpose": intended_purpose},
        )
        if status >= 400:
            err_console.print(f"[red]Service error ({status}):[/red] {data}")
            sys.exit(2 if status == 422 else 3)
        if output == OutputFormat.json:
            console.print_json(json.dumps(data))
        else:
            color = (
                "red" if data.get("risk_class") in ("high", "unacceptable") else "green"
            )
            console.print(
                f"Risk class: [bold {color}]{str(data.get('risk_class', '')).upper()}[/bold {color}]"
            )
        sys.exit(0)
    except ConnectionError:
        pass

    assessment_input = AssessmentInput(
        model=ModelMetadata(
            name=system_id,
            version="1.0.0",
            modality="text",
            use_case=intended_purpose,
            deployment_context="classification",
        )
    )
    result = assess(assessment_input)
    if output == OutputFormat.json:
        console.print_json(result.model_dump_json(indent=2))
    else:
        color = "red" if result.rules_failed else "green"
        console.print(
            f"Risk level: [bold {color}]{result.risk_level.value.upper()}[/bold {color}]"
        )
        console.print(result.evidence_summary)


@app.command("verify-output")
def verify_output_cmd(
    system_id: str = typer.Option(..., "--system-id"),
    claim_ref: str = typer.Option("manual", "--claim-ref"),
    source_ref: str = typer.Option("offline://manual", "--source-ref"),
    expected_value: str | None = typer.Option(None, "--expected-value"),
    claim_file: Path | None = typer.Option(None, "--claim-file"),
) -> None:
    """Verify an AI output claim against ground-truth sources (REQ-GTVG-001)."""
    if claim_file is not None:
        claim_ref = claim_file.name
        source_ref = str(claim_file)

    payload: dict = {
        "system_id": system_id,
        "claim_ref": claim_ref,
        "source_ref": source_ref,
    }
    if expected_value is not None:
        payload["expected_value"] = expected_value

    try:
        status, data = _call_service("/v1/verify/claims", payload)
        if status >= 400:
            err_console.print(f"[red]Service error ({status}):[/red] {data}")
            sys.exit(2 if status == 422 else 3)
        console.print_json(json.dumps(data))
        sys.exit(0)
    except ConnectionError:
        err_console.print(
            "[yellow]verify-output requires the risk-engine service.[/yellow]\n"
            "Set OPENCOMPLAI_API_URL and ensure the Docker Compose stack is running."
        )
        sys.exit(3)


@docs_app.command("generate")
def docs_generate_cmd(
    system_id: str = typer.Option(..., "--system-id"),
    commit_ref: str = typer.Option("HEAD", "--commit-ref"),
    intended_purpose: str = typer.Option("Not specified", "--intended-purpose"),
    provider_name: str = typer.Option("Unknown Provider", "--provider-name"),
    manifest_file: Path | None = typer.Option(
        None,
        "--manifest",
        "-m",
        help=(
            "Path to the system manifest written by `opencomplai init`. "
            "When set, the manifest's Section 2/3 fields are sent to the "
            "doc-generator so the dossier reflects the real system."
        ),
    ),
    output_dir: Path = typer.Option(Path("."), "--output-dir"),
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """Generate an Annex IV technical documentation dossier (REQ-DOC-001)."""
    # Optional manifest passthrough so Section 2/3 inputs reach the generator.
    loaded_manifest: SystemManifest | None = None
    if manifest_file is not None:
        if not manifest_file.exists():
            err_console.print(
                f"[red]Error:[/red] manifest file not found: {manifest_file}"
            )
            sys.exit(2)
        try:
            loaded_manifest = SystemManifest.model_validate_json(
                manifest_file.read_text()
            )
        except Exception as exc:
            err_console.print(f"[red]Invalid manifest:[/red] {exc}")
            sys.exit(2)

    payload: dict = {
        "system_id": system_id,
        "commit_ref": commit_ref,
        "intended_purpose": intended_purpose,
        "provider_name": provider_name,
    }
    if loaded_manifest is not None:
        payload.update(
            {
                "high_risk_presumption": loaded_manifest.high_risk_presumption,
                "training_data_description": loaded_manifest.training_data_description,
                "model_architecture": loaded_manifest.model_architecture,
                "performance_metrics": loaded_manifest.performance_metrics,
                "known_limitations": loaded_manifest.known_limitations,
                "human_oversight_measures": loaded_manifest.human_oversight_measures,
                "monitoring_approach": loaded_manifest.monitoring_approach,
                "incident_response_procedure": loaded_manifest.incident_response_procedure,
            }
        )

    try:
        status, data = _call_service("/v1/docs/generate", payload)
        if status >= 400:
            err_console.print(f"[red]Service error ({status}):[/red] {data}")
            sys.exit(2 if status == 422 else 3)
        if output == OutputFormat.json:
            console.print_json(json.dumps(data))
        else:
            valid_marker = (
                "[green]valid[/green]"
                if data.get("schema_valid")
                else "[red]invalid[/red]"
            )
            console.print("\n[bold]Annex IV Dossier Generated[/bold]")
            console.print(f"  dossier_id:      {data.get('dossier_id')}")
            console.print(f"  bundle_checksum: {data.get('bundle_checksum')}")
            console.print(f"  schema:          {valid_marker}")
            console.print(f"  duration_ms:     {data.get('duration_ms')}")
        # HIGH-risk guardrail: warn loudly when section2_complete=false
        if data.get("section2_complete") is False:
            err_console.print(
                "[yellow]WARN:[/yellow] section2_complete=false — "
                "HIGH risk classification requires populated Section 2 "
                "(training_data_description, model_architecture) before audit. "
                "Re-run with --manifest pointing to a fully populated manifest."
            )
        sys.exit(0)
    except ConnectionError:
        pass

    # Local fallback
    try:
        from opencomplai_core.engine import assess as _assess
        from opencomplai_doc_generator.generator import (
            generate_dossier,
            validate_dossier_schema,
        )

        manifest = (
            loaded_manifest.model_copy(update={"commit_ref": commit_ref})
            if loaded_manifest is not None
            else SystemManifest(
                system_id=system_id,
                intended_purpose=intended_purpose,
                compliance_target="EU_AI_ACT",
                high_risk_presumption=False,
                commit_ref=commit_ref,
            )
        )
        risk_result = _assess(
            AssessmentInput(
                model=ModelMetadata(
                    name=system_id,
                    version=commit_ref,
                    modality="text",
                    use_case=intended_purpose,
                    deployment_context="production",
                )
            )
        )
        dossier = generate_dossier(manifest, risk_result, provider_name=provider_name)
        schema_valid = validate_dossier_schema(dossier)

        output_dir.mkdir(parents=True, exist_ok=True)
        out_file = output_dir / f"dossier_{dossier.dossier_id}.json"
        out_file.write_text(dossier.model_dump_json(indent=2))

        if output == OutputFormat.json:
            console.print_json(dossier.model_dump_json(indent=2))
        else:
            valid_marker = (
                "[green]valid[/green]" if schema_valid else "[red]invalid[/red]"
            )
            console.print("\n[bold]Annex IV Dossier Generated (local)[/bold]")
            console.print(f"  dossier_id:      {dossier.dossier_id}")
            console.print(f"  bundle_checksum: {dossier.bundle_checksum}")
            console.print(f"  schema:          {valid_marker}")
            console.print(f"  output:          {out_file}")
        # HIGH-risk guardrail: warn loudly when section2_complete=false
        if not dossier.section2_complete:
            err_console.print(
                "[yellow]WARN:[/yellow] section2_complete=false — "
                "HIGH risk classification requires populated Section 2 "
                "(training_data_description, model_architecture) before audit. "
                "Re-run with --manifest pointing to a fully populated manifest."
            )
        sys.exit(0)
    except Exception as exc:
        err_console.print(f"[red]Dossier generation failed:[/red] {exc}")
        sys.exit(1)


@sync_app.command("metadata")
def sync_metadata_cmd(
    system_id: str = typer.Option(..., "--system-id"),
    endpoint: str | None = typer.Option(None, "--endpoint"),
) -> None:
    """Sync allowlisted metadata to the premium dashboard (Phase 18)."""
    try:
        status, data = _call_service(
            "/v1/sync/metadata",
            {"system_id": system_id},
        )
        if status >= 400:
            err_console.print(f"[red]Service error ({status}):[/red] {data}")
            sys.exit(3)
        console.print_json(json.dumps(data))
        sys.exit(0)
    except ConnectionError:
        err_console.print(
            "[yellow]sync metadata requires the egress-proxy service.[/yellow]\n"
            "Set OPENCOMPLAI_API_URL and ensure the Docker Compose stack is running."
        )
        sys.exit(3)


def _print_human(result) -> None:
    """Print a human-readable assessment report to the terminal."""
    console.print("\n[bold]Opencomplai Assessment Report[/bold]")
    console.print(f"Model:      {result.model_name} v{result.model_version}")
    color = "red" if result.rules_failed else "green"
    console.print(
        f"Risk level: [bold {color}]{result.risk_level.value.upper()}[/bold {color}]"
    )
    console.print(
        f"Rules:      {result.rules_passed} passed, "
        f"{result.rules_failed} failed of {result.rules_evaluated} total"
    )
    console.print(f"Generated:  {result.generated_at}\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Rule", style="dim", max_width=40)
    table.add_column("Status", min_width=6)
    table.add_column("Reference", style="dim")
    table.add_column("Rationale")

    for rule in result.rule_results:
        status = "[green]PASS[/green]" if rule.passed else "[red]FAIL[/red]"
        table.add_row(rule.rule_name, status, rule.reference, rule.rationale)

    console.print(table)
    console.print(f"\n{result.evidence_summary}\n")


# ---------------------------------------------------------------------------
# keys sub-commands
# ---------------------------------------------------------------------------


@keys_app.command("rotate")
def keys_rotate_cmd(
    output: OutputFormat = typer.Option(OutputFormat.human, "--output", "-o"),
) -> None:
    """
    Rotate the local Ed25519 signing keypair (ISO 27001 A.8.24 / FedRAMP SC-12).

    Generates a new keypair in ~/.opencomplai/, archives the old private key
    as signing.key.prev, and prints the new public key fingerprint.
    Recommend running every 90 days. See docs/security/key-management.md.
    """
    import hashlib
    import shutil

    if not _SIGNING_KEY.exists():
        err_console.print(
            "[red]Error:[/red] No signing key found. Run [bold]opencomplai init[/bold] first."
        )
        sys.exit(2)

    try:
        from opencomplai_core.signing import generate_keypair
    except ImportError:
        err_console.print(
            "[red]Error:[/red] cryptography package not installed. "
            "Run: pip install cryptography"
        )
        sys.exit(1)

    # Archive the old key
    prev_key_path = _OPENCOMPLAI_DIR / "signing.key.prev"
    prev_pub_path = _OPENCOMPLAI_DIR / "signing.pub.prev"
    shutil.copy2(_SIGNING_KEY, prev_key_path)
    prev_key_path.chmod(0o600)
    if _SIGNING_PUB.exists():
        shutil.copy2(_SIGNING_PUB, prev_pub_path)

    # Generate new keypair (overwrites signing.key + signing.pub)
    new_install_id = generate_keypair(_OPENCOMPLAI_DIR)

    # Compute public key fingerprint (SHA-256 of PEM bytes)
    pub_bytes = _SIGNING_PUB.read_bytes()
    fingerprint = hashlib.sha256(pub_bytes).hexdigest()[:16]

    # Update config with new install_id
    cfg = _load_config()
    cfg["install_id"] = new_install_id
    _write_config(cfg)

    if output == OutputFormat.json:
        console.print_json(
            json.dumps(
                {
                    "status": "rotated",
                    "new_install_id": new_install_id,
                    "public_key_fingerprint": fingerprint,
                    "archived_to": str(prev_key_path),
                }
            )
        )
    else:
        console.print("\n[bold green]Signing key rotated successfully[/bold green]")
        console.print(f"  new install_id:        {new_install_id}")
        console.print(f"  public key fingerprint: sha256:{fingerprint}...")
        console.print(f"  old key archived to:    {prev_key_path}")
        console.print(
            "\n[dim]Update your SaaS dashboard enrollment with the new public key.[/dim]"
        )


# ---------------------------------------------------------------------------
# ai sub-commands (requires opencomplai-ai)
# ---------------------------------------------------------------------------


def _require_ai_plugin() -> None:
    try:
        import opencomplai_ai  # noqa: F401
    except ImportError:
        err_console.print(
            "[red]Error:[/red] opencomplai-ai is not installed.\n"
            "  Basic:  pip install opencomplai-ai\n"
            "  Full:   pip install 'opencomplai-ai[deep]'"
        )
        sys.exit(1)


@ai_app.command("configure")
def ai_configure_cmd(
    model: str | None = typer.Option(
        None, "--model", help="Model ID to set as default"
    ),
    set_default: bool = typer.Option(
        False, "--set-default", help="Save the chosen model"
    ),
) -> None:
    """Configure the active AI intent model (interactive or via --model)."""
    _require_ai_plugin()
    from opencomplai_ai.config import set_active_model
    from opencomplai_ai.models import MODEL_CATALOG

    if model:
        if model not in MODEL_CATALOG:
            err_console.print(
                f"[red]Error:[/red] Unknown model '{model}'. "
                f"Valid: {', '.join(MODEL_CATALOG)}"
            )
            sys.exit(2)
        chosen = model
    else:
        import questionary

        choices = []
        for mid, spec in MODEL_CATALOG.items():
            label = f"{mid:<28} [{spec.size_mb} MB,  {spec.license},  {spec.runtime}]"
            if mid == "qwen2.5-coder-1.5b":
                label += "  ← recommended"
            if mid == "codebert-onnx":
                label += "  ← fastest, no llama-cpp"
            choices.append(questionary.Choice(title=label, value=mid))

        chosen = questionary.select(
            "Choose an AI intent model:",
            choices=choices,
            default="qwen2.5-coder-1.5b",
        ).ask()
        if chosen is None:
            sys.exit(0)

        if set_default or questionary.confirm("Save as default?", default=True).ask():
            set_active_model(chosen)
            console.print(f"[green]Default model set to:[/green] {chosen}")
            return

    if set_default:
        set_active_model(chosen)
        console.print(f"[green]Default model set to:[/green] {chosen}")
    else:
        console.print(
            f"Selected model: {chosen}  (not saved — pass --set-default to persist)"
        )


@ai_app.command("status")
def ai_status_cmd() -> None:
    """Show the active AI intent model, cache location, and disk usage."""
    _require_ai_plugin()
    from opencomplai_ai.config import get_active_model, get_cache_dir
    from opencomplai_ai.models import MODEL_CATALOG

    active = get_active_model()
    spec = MODEL_CATALOG.get(active)
    cache_dir = get_cache_dir()

    console.print("\n[bold]AI Intent Plugin Status[/bold]")
    console.print(f"  active model  : {active}")
    if spec:
        console.print(f"  display name  : {spec.display_name}")
        console.print(f"  size          : ~{spec.size_mb} MB")
        console.print(f"  runtime       : {spec.runtime}")
        console.print(f"  license       : {spec.license}")
        deep_status = (
            "[green]installed[/green]"
            if _deep_installed()
            else "[yellow]not installed[/yellow] (run: pip install 'opencomplai-ai\\[deep]')"
        )
        if spec.requires_deep:
            console.print(f"  llama-cpp     : {deep_status}")
    console.print(f"  cache dir     : {cache_dir}")

    if cache_dir.exists():
        total = sum(f.stat().st_size for f in cache_dir.iterdir() if f.is_file())
        console.print(f"  cache size    : {total // (1024 * 1024)} MB")
        cached = [f.name for f in cache_dir.iterdir() if f.is_file()]
        if cached:
            console.print(f"  cached files  : {', '.join(cached)}")
    else:
        console.print("  cache dir     : (empty — model not yet downloaded)")
    console.print()


def _deep_installed() -> bool:
    try:
        import llama_cpp  # noqa: F401

        return True
    except ImportError:
        return False


def _preload_ai_model(model_id: str | None) -> bool:
    """Ensure the AI model is cached before Rich's live display starts.

    Interactive download/export prompts must be shown BEFORE progress bars are
    active; Rich's live renderer hides console.input() on most terminals.
    Returns False if the user cancels or a hard dependency is missing (caller
    should set ai_intent=False so the scan still completes without AI).
    """
    try:
        from opencomplai_ai.config import get_active_model
        from opencomplai_ai.downloader import ensure_model

        resolved = model_id or get_active_model()
        ensure_model(resolved)
        return True
    except ImportError:
        return True  # plugin not installed; run_scan will emit the warning
    except RuntimeError as exc:
        err_console.print(f"[yellow]AI intent skipped:[/yellow] {exc}")
        return False
