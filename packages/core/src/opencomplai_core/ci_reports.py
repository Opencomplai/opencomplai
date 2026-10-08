"""CI report renderers for the `check` verdict: JUnit XML, Markdown summary, SARIF.

Pure functions of the compliance-artifact dict (what `model_dump(mode="json")`
or the on-disk `compliance-artifact.json` gives). No I/O, no clock, no env: the
outputs never print `generated_at` or any other date (E-14), and they add no
compliance content, only re-render fields already in the artifact (E-15).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter

from opencomplai_core.frameworks import EU_AI_ACT, framework_of
from opencomplai_core.scanner.sarif import SARIF_SCHEMA_URI, SARIF_VERSION

_HEURISTIC = "Heuristic projection, not a compliance verdict."
_GAP_LEVELS = {"missing": "error", "partial": "warning", "unverified": "note"}


def summarize_failed_controls(ids: list[str], limit: int | None = None) -> str:
    """`failed_controls` for a CI message: the EU AI Act ids (the first
    `limit` of them), then "<FW>: N requirement(s)" per gated framework.

    Without prefixed ids this is the plain comma-joined list it always was.
    """
    ids = [str(c) for c in ids]
    eu = [c for c in ids if framework_of(c) == EU_AI_ACT]
    others = Counter(framework_of(c) for c in ids if framework_of(c) != EU_AI_ACT)
    return ", ".join(
        [*eu[:limit], *(f"{fw}: {n} requirement(s)" for fw, n in others.items())]
    )


def artifact_to_junit(artifact: dict | None, detail: str = "") -> str:
    """One testsuite, one testcase; a <failure> for every CI-failing result."""
    suite = ET.Element("testsuite", name="opencomplai", tests="1")
    case = ET.SubElement(
        suite, "testcase", name="compliance-scan", classname="opencomplai"
    )

    if artifact:
        result = artifact.get("result", "unknown")
        message = None
        if result == "control_fail":
            failed = artifact.get("failed_controls", [])
            message = f"control_fail: {summarize_failed_controls(failed)}"
        elif result == "trap_detected":
            # trap_detected fails the build (exit 4): report it as a failure so
            # the JUnit case does not stay green while the pipeline goes red.
            message = (
                "trap_detected — Article 25 deployment freeze, HITL review required"
            )
        elif result == "policy_block":
            message = "policy_block — prohibited system (EU AI Act Article 5)"
        elif result == "validation_fail":
            message = "validation_fail — manifest or input validation error"
        if message is not None:
            ET.SubElement(case, "failure", message=message).text = detail
    else:
        ET.SubElement(case, "error", message="No artifact result parsed")

    return ET.tostring(suite, encoding="unicode", xml_declaration=False)


def artifact_to_summary_md(artifact: dict | None) -> str:
    """Markdown job summary table (what the GitHub connector shows)."""
    result = artifact.get("result", "unknown") if artifact else "unknown"
    system_id = artifact.get("system_id", "unknown") if artifact else "unknown"
    commit_ref = artifact.get("commit_ref", "") if artifact else ""
    lines = [
        "## Opencomplai Compliance Scan",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Result | `{result}` |",
        f"| System | `{system_id}` |",
        f"| Commit | `{commit_ref}` |",
    ]
    if artifact and artifact.get("failed_controls"):
        failed = summarize_failed_controls(artifact["failed_controls"], limit=5)
        lines.append(f"| Failed controls | `{failed}` |")
    eval_summary = artifact.get("eval_summary") if artifact else None
    if isinstance(eval_summary, dict):
        lines.append(
            f"| Eval outcome | `{eval_summary.get('overall_outcome', 'n/a')}` |"
        )
    elif artifact and artifact.get("eval_overall_outcome"):
        lines.append(f"| Eval outcome | `{artifact['eval_overall_outcome']}` |")
    return "\n".join(lines)


def artifact_to_sarif(
    artifact: dict,
    location_uri: str = "system-manifest.json",
    tool_version: str = "",
) -> dict:
    """SARIF 2.1.0 of the check verdict (failed controls + non-met gap rows)."""
    location = [
        {
            "physicalLocation": {
                "artifactLocation": {"uri": location_uri},
                "region": {"startLine": 1},
            }
        }
    ]
    rules: dict[str, dict] = {}
    results: list[dict] = []

    def add(rule_id: str, rule_text: str, level: str, text: str) -> None:
        rules.setdefault(
            rule_id,
            {"id": rule_id, "name": rule_id, "shortDescription": {"text": rule_text}},
        )
        results.append(
            {
                "ruleId": rule_id,
                "level": level,
                "message": {"text": text},
                "locations": location,
            }
        )

    for control in artifact.get("failed_controls") or []:
        control = str(control)
        add(
            control,
            f"Failed control {control}",
            "error",
            f"Control {control} failed the compliance check.",
        )

    gap_report = artifact.get("gap_report")
    for row in (gap_report or {}).get("articles") or []:
        level = _GAP_LEVELS.get(row.get("status"))
        if level is None:  # met (or unknown): nothing to report
            continue
        ref = str(row.get("evidence_ref") or "none")
        article = row.get("article") or "article"
        rationale = row.get("rationale") or f"{article}: status {row.get('status')}."
        add(
            f"gap/{ref}",
            f"Gap row for evidence {ref}",
            level,
            f"{article}: {rationale} {_HEURISTIC}",
        )

    driver: dict = {
        "name": "opencomplai",
        "informationUri": "https://opencomplai.com",
        "rules": list(rules.values()),
    }
    if tool_version:
        driver["version"] = tool_version
    return {
        "$schema": SARIF_SCHEMA_URI,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {"driver": driver},
                "results": results,
                "properties": {
                    "opencomplai_result": artifact.get("result"),
                    "system_id": artifact.get("system_id"),
                    "commit_ref": artifact.get("commit_ref"),
                },
            }
        ],
    }
