"""EU AI Act compliance checker CLI wizard and results display."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer
from opencomplai_core.compliance_checker import (
    CHECKER_VERSION,
    CheckerSession,
    ComplianceCheckerResult,
    EntityType,
    evaluate,
    export_all,
    render_json,
    render_markdown,
    render_pdf,
)
from opencomplai_core.compliance_checker.catalog import load_help_content
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
err_console = Console(stderr=True)

DISCLAIMER = (
    "Opencomplai is not affiliated with the Future of Life Institute or the European Union. "
    "Results are informational only — not legal advice. Seek professional legal counsel."
)

ENTITY_LABELS = {
    EntityType.PROVIDER.value: "Provider",
    EntityType.DEPLOYER.value: "Deployer",
    EntityType.DISTRIBUTOR.value: "Distributor",
    EntityType.IMPORTER.value: "Importer",
    EntityType.PRODUCT_MANUFACTURER.value: "Product manufacturer",
    EntityType.AUTHORISED_REP.value: "Authorised representative",
}


def _confirm(label: str, *, default: bool = False) -> bool:
    try:
        import questionary

        return questionary.confirm(label, default=default).ask() or False
    except ImportError:
        return typer.confirm(label, default=default)


def _select(label: str, choices: list[tuple[str, str]]) -> str:
    """Return the choice value (first element of tuple)."""
    try:
        import questionary

        options = [
            questionary.Choice(title=title, value=value) for value, title in choices
        ]
        result = questionary.select(label, choices=options).ask()
        if result is None:
            raise typer.Abort()
        return result
    except ImportError:
        console.print(f"\n[bold]{label}[/bold]")
        for idx, (_value, title) in enumerate(choices, start=1):
            console.print(f"  {idx}. {title}")
        raw = typer.prompt("Enter number", type=int)
        if raw < 1 or raw > len(choices):
            raise typer.BadParameter("Invalid selection") from None
        return choices[raw - 1][0]


def _show_help(section_key: str) -> None:
    help_data = load_help_content()
    section = help_data.get(section_key)
    if not section:
        return
    console.print(
        Panel(
            section.get("body", ""),
            title=section.get("title", section_key),
            border_style="blue",
        )
    )


def _show_entity_guide() -> None:
    help_data = load_help_content()
    body = help_data.get("entity_definitions", {}).get("body", "")
    console.print(Panel(body, title="Operator roles (Article 3)", border_style="cyan"))


def run_interactive_wizard(*, skip_allowed: bool = True) -> CheckerSession | None:
    """Collect answers via terminal prompts. Returns None if skipped."""
    console.print(
        Panel(
            "This wizard determines how the EU AI Act may apply to your AI system.\n"
            "Press Ctrl+C to abort. Type '?' at any prompt for help (where supported).",
            title="EU AI Act Compliance Checker",
            border_style="green",
        )
    )
    if skip_allowed and _confirm(
        "Skip applicability check and continue without checker?", default=False
    ):
        return None

    answers: dict[str, Any] = {}

    _show_help("ai_system_definition")
    answers["gate_is_ai_system"] = _confirm(
        "Is your system an 'AI system' under the EU AI Act (Article 3(1))?",
        default=True,
    )
    if not answers["gate_is_ai_system"]:
        return CheckerSession(answers=answers)

    _show_entity_guide()
    entity = _select(
        "Which kind of entity is your organisation?",
        [(e.value, ENTITY_LABELS[e.value]) for e in EntityType],
    )
    answers["e1_entity_type"] = entity

    if entity == EntityType.AUTHORISED_REP.value:
        return CheckerSession(answers=answers)

    if entity == EntityType.PRODUCT_MANUFACTURER.value:
        integration = _select(
            "Does your product integrate an AI system under your manufacturer name?",
            [
                (
                    "integrated",
                    "Yes — placed on market or put into service with my product",
                ),
                ("none", "No — none of the above"),
            ],
        )
        answers["e3_product_integration"] = integration
        if integration == "none":
            return CheckerSession(answers=answers)
    else:
        _show_help("modifications_overview")
        answers["e2_modifications"] = _confirm(
            "Do you (or a downstream operator) make substantial modifications to the system?",
            default=False,
        )

    _show_help("high_risk_overview")
    answers["hr1_annex_i"] = _confirm(
        "Is the system a product with AI as safety component under Annex I harmonisation law?",
        default=False,
    )
    answers["hr2_annex_iii"] = _confirm(
        "Does the system fall within an Annex III high-risk use case?",
        default=False,
    )
    if answers["hr1_annex_i"] or answers["hr2_annex_iii"]:
        answers["hr3_art_6_3"] = _confirm(
            "Does Article 6(3) apply (safety component required for product conformity)?",
            default=False,
        )
        answers["hr4_narrow_task"] = _confirm(
            "Is the AI intended only for a narrow procedural task (Art 6(3) exception)?",
            default=False,
        )
        answers["hr5_no_significant_risk"] = _confirm(
            "Does the system NOT pose significant risk to health, safety, or fundamental rights?",
            default=False,
        )
        answers["hr6_accessory"] = _confirm(
            "Is the system purely accessory to the relevant human decision (Art 6(3))?",
            default=False,
        )

    _show_help("scope_overview")
    answers["s1_in_scope"] = _confirm(
        "Are you placing, deploying, or using the system's output in the EU?",
        default=True,
    )
    if not answers["s1_in_scope"]:
        return CheckerSession(answers=answers)

    answers["s1_scope_region"] = _select(
        "Where is your organisation established?",
        [
            ("eu", "Established or located in the EU"),
            ("third_country", "Outside the EU"),
        ],
    )

    _show_help("gpai_overview")
    answers["s1_gpai"] = _confirm(
        "Are you placing a General-Purpose AI model on the EU market?",
        default=False,
    )
    if answers["s1_gpai"]:
        answers["s1_gpai_systemic_risk"] = _confirm(
            "Does the GPAI model have systemic risk (high impact capabilities)?",
            default=False,
        )

    answers["r2_excluded"] = _confirm(
        "Is the system excluded (military, R&D only, open-source not yet placed, personal use)?",
        default=False,
    )
    if answers["r2_excluded"]:
        return CheckerSession(answers=answers)

    answers["r3_prohibited"] = _confirm(
        "Does the system perform prohibited practices under Article 5?",
        default=False,
    )
    if answers["r3_prohibited"]:
        return CheckerSession(answers=answers)

    answers["r4_transparency"] = _confirm(
        "Does the system require transparency obligations (chatbot, deepfake, synthetic content)?",
        default=False,
    )

    if entity == EntityType.DEPLOYER.value:
        answers["r5_fria"] = _confirm(
            "Are you a public body or private entity providing public services (FRIA under Art 27)?",
            default=False,
        )

    return CheckerSession(answers=answers)


def display_results(result: ComplianceCheckerResult) -> None:
    """Render human-readable results with glossary."""
    headline_parts: list[str] = []
    if result.is_prohibited:
        headline_parts.append("[red]Prohibited[/red]")
    elif result.is_high_risk:
        headline_parts.append("[yellow]High risk[/yellow]")
    elif result.in_scope:
        headline_parts.append("[green]In scope[/green]")
    else:
        headline_parts.append("[dim]Out of scope[/dim]")
    if result.effective_entity:
        headline_parts.append(
            f"— {ENTITY_LABELS.get(result.effective_entity.value, result.effective_entity.value)}"
        )

    console.print(
        Panel(
            " ".join(headline_parts),
            title="EU AI Act Applicability Result",
            border_style="bold",
        )
    )

    if result.status_changes:
        st = Table(title="Status changes")
        st.add_column("Status")
        st.add_column("Description")
        for item in result.status_changes:
            st.add_row(f"[bold]{item.title}[/bold]", item.body)
        console.print(st)

    if result.obligations:
        ot = Table(title="Your obligations")
        ot.add_column("Obligation")
        ot.add_column("Reference")
        ot.add_column("Summary")
        for item in result.obligations:
            summary = item.body[:120] + ("…" if len(item.body) > 120 else "")
            ot.add_row(item.title, item.article_ref, summary)
        console.print(ot)

    help_data = load_help_content()
    glossary = help_data.get("entity_definitions", {})
    if glossary:
        console.print(
            Panel(
                glossary.get("body", ""),
                title="What these terms mean",
                border_style="dim",
            )
        )

    console.print(f"\n[dim]{DISCLAIMER}[/dim]\n")


def evaluate_and_finalize(session: CheckerSession) -> ComplianceCheckerResult:
    result = evaluate(session)
    result.answers = dict(session.answers)
    result.session_id = str(uuid.uuid4())
    return result


def write_exports(
    result: ComplianceCheckerResult,
    *,
    export_json: Path | None = None,
    export_md: Path | None = None,
    export_pdf: Path | None = None,
    export_all_base: Path | None = None,
) -> None:
    if export_all_base is not None:
        parent = export_all_base.parent
        base = export_all_base.stem
        paths = export_all(result, parent, basename=base)
        console.print(f"Exported: {paths['json']}, {paths['markdown']}, {paths['pdf']}")
        return
    if export_json:
        export_json.write_text(render_json(result), encoding="utf-8")
        console.print(f"Wrote JSON: {export_json}")
    if export_md:
        export_md.write_text(render_markdown(result), encoding="utf-8")
        console.print(f"Wrote Markdown: {export_md}")
    if export_pdf:
        try:
            export_pdf.write_bytes(render_pdf(result))
            console.print(f"Wrote PDF: {export_pdf}")
        except ImportError as exc:
            err_console.print(f"[yellow]PDF export skipped:[/yellow] {exc}")


def load_answers_file(path: Path) -> CheckerSession:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "answers" in raw:
        return CheckerSession(answers=raw["answers"])
    return CheckerSession(answers=raw)


def build_checker_session_ref(
    result: ComplianceCheckerResult,
    report_json_path: Path | None = None,
) -> dict[str, str]:
    return {
        "checker_version": CHECKER_VERSION,
        "session_id": result.session_id or str(uuid.uuid4()),
        "completed_at": datetime.now(UTC).isoformat(),
        "report_json_path": str(report_json_path) if report_json_path else "",
    }
