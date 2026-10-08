"""Agent inventory report: pure functions, no I/O, no clock (E-14).

Reads what the manifest declares (`check_inventory`) and, when a scan report is
supplied, cross-checks it with `agent_sources.cross_check`. It never produces a
verdict: a declaration is labelled `declared`, a scan finding `detected`.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from opencomplai_core.agent_inventory import check_inventory
from opencomplai_core.agent_responsibility import get_responsibilities
from opencomplai_core.agent_sources import cross_check, detected
from opencomplai_core.models import CorroborationReport, SystemManifest

NOT_A_VERDICT = "evidence only; not a compliance verdict"
DRAFT_NOTE = (
    "The reference responsibility rows are draft content awaiting founder "
    "review (unverified wording, lawyer to confirm)."
)
_AGENT_ID = re.compile(r"agent '([^']+)'")


def build_agent_report(
    manifest: SystemManifest, scan_report: CorroborationReport | None = None
) -> dict[str, Any]:
    inv = manifest.agent_inventory
    inventory: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    declared_map = None
    if inv is not None:
        for a in inv.agents:
            inventory.append(
                {
                    "id": a.id,
                    "name": a.name,
                    "parent_id": a.parent_id,
                    "tools": [t.name for t in a.tools],
                    "models": [f"{m.provider}/{m.model}" for m in a.models],
                    "has_mandate": a.mandate is not None,
                    "guardrail_count": len(a.guardrails),
                }
            )
        for err in check_inventory(inv):
            m = _AGENT_ID.search(err)
            findings.append(
                {
                    "kind": "invalid_inventory",
                    "evidence": "declared",
                    "id": m.group(1) if m else "",
                    "detail": err,
                }
            )
        if inv.responsibility_map is not None:
            declared_map = inv.responsibility_map.model_dump()
        if scan_report is not None:
            check = cross_check(inv, detected(scan_report))
            findings += [
                {
                    "kind": "detected_not_declared",
                    "evidence": "detected",
                    "id": x,
                    "detail": f"{x} found by the scan, not declared in the manifest",
                }
                for x in check.undeclared
            ]
            findings += [
                {
                    "kind": "declared_not_detected",
                    "evidence": "declared",
                    "id": x,
                    "detail": f"{x} declared in the manifest, not found by the scan",
                }
                for x in check.unseen
            ]
    return {
        "system_id": manifest.system_id,
        "notice": NOT_A_VERDICT,
        "inventory": inventory,
        "findings": findings,
        "responsibility_map": {
            "declared": declared_map,
            "reference_rows": [asdict(r) for r in get_responsibilities()],
            "reference_note": DRAFT_NOTE,
        },
    }


def render_agent_report_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Agent report: {report['system_id']}", "", f"_{report['notice']}_", ""]
    lines += ["## Inventory", ""]
    if not report["inventory"]:
        lines += ["No agent inventory declared.", ""]
    else:
        lines += [
            "| Agent | Parent | Tools | Models | Mandate | Guardrails |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for a in report["inventory"]:
            lines.append(
                f"| {a['id']} | {a['parent_id'] or '-'} | {', '.join(a['tools']) or '-'} "
                f"| {', '.join(a['models']) or '-'} | {'yes' if a['has_mandate'] else 'no'} "
                f"| {a['guardrail_count']} |"
            )
        lines.append("")
    lines += ["## Findings", ""]
    lines += [
        f"- [{f['evidence']}] {f['kind']}: {f['detail']}" for f in report["findings"]
    ] or ["None."]
    rmap = report["responsibility_map"]
    lines += ["", "## Responsibility map", "", rmap["reference_note"], ""]
    if rmap["declared"]:
        lines.append("Declared in the manifest:")
        for key, items in rmap["declared"].items():
            lines += [f"- {key}: {item}" for item in items]
        lines.append("")
    for r in rmap["reference_rows"]:
        lines.append(
            f"- {r['id']} ({r['party']}; {r['regime_ref']}): {r['summary']} "
            f"needs_founder_review: {str(r['needs_founder_review']).lower()}; "
            f"confidence: {r['confidence']}; source: {r['source']}"
        )
    return "\n".join(lines) + "\n"
