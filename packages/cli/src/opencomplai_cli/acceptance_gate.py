"""Gate semantics for an accepted high-risk system.

Runs in `check` right after core `apply_acceptance` and before the halt block
and signing. With no valid acceptance record it returns the artifact untouched.
An acceptance acknowledges the Art. 6 classification only; it does not remove
any other obligation, so Missing EU gap rows still fail the check.
Art. 5 (POLICY_BLOCK) is never downgraded. An approved trap needs a valid
acceptance AND a trap approval for the same change context. No clock reads.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer
from opencomplai_core.acceptance import (
    ART6_CONTROL,
    CLASSIFICATION_ACCEPTANCE,
    TRAP_APPROVAL,
    evaluate_record,
    record_path,
    trusted_key_ids_from_env,
)
from opencomplai_core.engine import assess
from opencomplai_core.eval_engine import run_evals
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    acceptance_gate_failures,
    evaluate_targets,
)
from opencomplai_core.models import (
    AssessmentInput,
    ModelMetadata,
    ScanResult,
    ScanStatusArtifact,
    SystemManifest,
)

TRAP_CONTROL = "EU_AIA_ART25_MODIFICATION_TRAP"
_UNTOUCHED = (
    ScanResult.POLICY_BLOCK,
    ScanResult.VALIDATION_FAIL,
    ScanResult.DEGRADED_COMPLETE,
)


def _acceptance_state(
    manifest: SystemManifest, change_context: str | None, repo_root: Path
) -> tuple[bool, bool]:
    """(acceptance_valid, trap_approved). Reads `repo_root` only, never HOME."""
    root = repo_root.resolve()
    trusted = trusted_key_ids_from_env(os.environ)

    def status(record_type: str):
        path = record_path(root, manifest.system_id, record_type)
        return evaluate_record(path, manifest, record_type, trusted_key_ids=trusted)

    valid = status(CLASSIFICATION_ACCEPTANCE).state == "valid"
    trap = status(TRAP_APPROVAL)
    approved = (
        trap.state == "valid"
        and trap.record is not None
        and trap.record.get("change_context") == change_context
    )
    return valid, approved


def apply_acceptance_gate(
    artifact: ScanStatusArtifact,
    manifest: SystemManifest,
    *,
    repo_root: Path,
    commit_ref: str,
    change_context: str | None,
    scan_mode: str,
    corroboration_report=None,
    sample_set=None,
) -> tuple[ScanStatusArtifact, bool]:
    """Return (artifact, halt_suppressed); see the module docstring."""
    valid, approved = _acceptance_state(manifest, change_context, repo_root)
    if not valid or artifact.result in _UNTOUCHED:
        return artifact, False
    trap = artifact.result == ScanResult.TRAP_DETECTED
    if trap and not approved:
        return artifact, False  # exit 4 and halt, as today

    drop = {ART6_CONTROL, TRAP_CONTROL} if trap else {ART6_CONTROL}
    failed = [c for c in artifact.failed_controls if c not in drop]
    result = ScanResult.CONTROL_FAIL if trap else artifact.result
    if result == ScanResult.CONTROL_FAIL and not failed:
        result = ScanResult.PASS

    from opencomplai_cli.main import _answers_from_change_context  # avoids a cycle

    risk = assess(
        AssessmentInput(
            model=ModelMetadata(
                name=manifest.system_id,
                version=commit_ref,
                modality="text",
                use_case=manifest.intended_purpose,
                deployment_context=scan_mode,
            ),
            answers=_answers_from_change_context(change_context),
        )
    )
    eval_report = (
        run_evals(
            manifest.system_id,
            commit_ref,
            sample_set.model_copy(update={"commit_ref": commit_ref}),
        )
        if sample_set is not None
        else None
    )
    try:
        reports = evaluate_targets(
            manifest,
            [EU_AI_ACT],
            commit_ref=commit_ref,
            risk_result=risk,
            corroboration_report=corroboration_report,
            eval_report=eval_report,
            repo_root=repo_root.resolve(),
        )
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        sys.exit(2)
    # An approved trap also stops the Art. 25 row (sourced from the trap rule) failing.
    skip = ("Art. 6", "Art. 25") if trap else ("Art. 6",)
    missing = acceptance_gate_failures(reports[EU_AI_ACT].report, skip=skip)
    failed = list(dict.fromkeys([*failed, *missing]))
    if missing and result == ScanResult.PASS:
        result = ScanResult.CONTROL_FAIL
    return (
        artifact.model_copy(update={"result": result, "failed_controls": failed}),
        trap,
    )
