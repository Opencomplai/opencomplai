"""`checker --write-manifest`: create a manifest, or append roles to an existing one."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import typer
from opencomplai_core.compliance_checker import (
    ComplianceCheckerResult,
    bridge_to_manifest_fields,
)
from opencomplai_core.models import SystemManifest
from pydantic import ValidationError
from rich.console import Console

from opencomplai_cli.commands.checker import build_checker_session_ref, console

err_console = Console(stderr=True)

# Most severe first; an unknown old verdict ranks last.
_SEVERITY = (
    "prohibited_practice",
    "high_risk_ai_system",
    "limited_risk_transparency",
    "general_purpose_ai_model",
    "in_scope_ai_system",
    "out_of_scope",
)


def _rank(verdict: Any) -> int:
    return _SEVERITY.index(verdict) if verdict in _SEVERITY else len(_SEVERITY)


def _union(old: Any, new: Sequence[str]) -> list[str]:
    out = [x for x in old if isinstance(x, str)] if isinstance(old, list) else []
    out.extend(x for x in new if x not in out)
    return out


def _fail(message: str) -> typer.Exit:
    err_console.print(f"[red]{message}[/red]")
    return typer.Exit(2)


def _prompt_system_id() -> str:
    return typer.prompt("System ID", default="my-ai-system")


def write_or_append_manifest(
    path: Path,
    *,
    result: ComplianceCheckerResult,
    report_path: Path | None,
    roles: Sequence[str],
    rationale: Sequence[str],
    obligation_ids: Sequence[str],
    intended_purpose: str | None,
    prompt_system_id: Callable[[], str] = _prompt_system_id,
) -> None:
    bridged = bridge_to_manifest_fields(result)
    ref = build_checker_session_ref(
        result, report_path, obligation_ids=obligation_ids, rationale=rationale
    )

    if not path.exists():
        system_id = prompt_system_id()
        if intended_purpose is None:
            intended_purpose = typer.prompt("Intended purpose (what the system does)")
        payload: dict[str, Any] = {
            "system_id": system_id,
            "intended_purpose": intended_purpose,
            "compliance_target": "EU_AI_ACT",
            "high_risk_presumption": bridged["high_risk_presumption"],
            "commit_ref": "HEAD",
            "operator_role": bridged["operator_role"],
        }
        if roles:
            payload["operator_roles"] = list(roles)
        payload["checker_session"] = ref
    else:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise _fail(f"Cannot read manifest {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise _fail(f"Cannot append to manifest {path}: not a JSON object")
        if roles:
            payload["operator_roles"] = _union(
                payload.get("operator_roles")
                or ([payload["operator_role"]] if payload.get("operator_role") else []),
                roles,
            )
        payload.setdefault("operator_role", bridged["operator_role"])
        payload["high_risk_presumption"] = bool(
            payload.get("high_risk_presumption")
        ) or bool(bridged["high_risk_presumption"])
        if intended_purpose is not None:
            payload["intended_purpose"] = intended_purpose
        old = payload.get("checker_session")
        old = old if isinstance(old, dict) else {}
        session = dict(old)
        session.update(ref)
        if _rank(old.get("verdict")) < _rank(ref["verdict"]):
            session["verdict"] = old["verdict"]
        if report_path is None and old.get("report_json_path"):
            session["report_json_path"] = old["report_json_path"]
        for key, new in (("obligation_ids", obligation_ids), ("rationale", rationale)):
            merged = _union(old.get(key), new)
            if merged:
                session[key] = merged
        payload["checker_session"] = session

    try:
        SystemManifest.model_validate(payload)
    except ValidationError as exc:
        raise _fail(f"Manifest {path} would be invalid, not written: {exc}") from exc
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    console.print(f"[green]Manifest written to[/green] {path}")
