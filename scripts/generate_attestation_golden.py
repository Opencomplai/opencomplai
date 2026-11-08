#!/usr/bin/env python3
"""Generate packages/core/tests/fixtures/attestation_golden_statuses.json: the statuses the engine
gives a fixed set of recorded attestations, so a second implementation of the status rule can
be held to the engine's answer without importing it.

The records stand for what an organisation has recorded: active, draft, revoked, expired, not
applicable, organisation-wide and for one system. The generator ships the records an issuer
would put in a system's attestation bundle (active, in date on the day the bundle is issued,
a system record before an organisation one), merges the bundle into a manifest with
`opencomplai_cli.attestations.merge_into_manifest`, runs `evaluate_targets` on every native
pack, and writes the status of each row of interest. It also writes, per framework, the
requirement ids that only an attestation can decide, and the other ids that take one.

Run after editing a framework pack's data, the attestation merge or the status rules:
    python scripts/generate_attestation_golden.py

packages/core/tests/test_attestation_golden.py fails loud when the committed file is stale; so does
    python scripts/generate_attestation_golden.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from opencomplai_cli.attestations import merge_into_manifest
from opencomplai_core.attestation_bundle import AttestationBundle
from opencomplai_core.frameworks import (
    EU_AI_ACT,
    FRAMEWORKS,
    attestable_ids,
    attestation_only_ids,
    evaluate_targets,
    framework_of,
)
from opencomplai_core.models import (
    EvalReport,
    EvaluatorCategory,
    EvaluatorOutcome,
    EvaluatorResult,
    SystemManifest,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = (
    REPO_ROOT
    / "packages"
    / "core"
    / "tests"
    / "fixtures"
    / "attestation_golden_statuses.json"
)

TODAY = date(2026, 11, 3)  # the day the run is judged
ISSUED_ON = date(
    2026, 11, 1
)  # the day the bundle was issued; a pulled file can be older
SYSTEM = "golden-system"
OTHER_SYSTEM = "other-system"
ISO_27001 = "ISO_IEC_27001"
EU_PREFIX = f"{EU_AI_ACT}:"


def _record(
    rid: str,
    requirement_id: str,
    *,
    system_id: str | None = None,
    kind: str = "attested",
    status: str = "active",
    valid_until: str | None = None,
    statement: str | None = None,
) -> dict[str, Any]:
    return {
        "id": rid,
        "requirement_id": requirement_id,
        "system_id": system_id,
        "kind": kind,
        "status": status,
        "statement": statement or f"In place ({rid}).",
        "attested_by": "Jane Doe",  # a display name, never an email
        "attested_at": "2026-06-01",
        "valid_until": valid_until,
    }


A = f"{ISO_27001}:A.5."
RECORDS: list[dict[str, Any]] = [
    _record("rec-active", f"{ISO_27001}:A.6.3", valid_until="2027-06-01"),
    _record("rec-last-good-day", A + "3", valid_until=TODAY.isoformat()),
    _record("rec-expired-before-issue", A + "2", valid_until="2026-10-31"),
    _record("rec-expired-after-issue", A + "4", valid_until="2026-11-02"),
    _record("rec-draft", A + "1", status="draft"),
    _record("rec-revoked", A + "5", status="revoked"),
    _record(
        "rec-not-applicable",
        "SOC_2:CC1.1",
        kind="not_applicable",
        statement="The company has no office.",
    ),
    _record("rec-organisation", A + "6"),
    _record("rec-system", A + "6", system_id=SYSTEM),
    _record("rec-organisation-active", A + "7"),
    _record("rec-system-draft", A + "7", system_id=SYSTEM, status="draft"),
    _record("rec-other-system", A + "8", system_id=OTHER_SYSTEM),
    _record("rec-system-only", A + "9", system_id=SYSTEM),
    _record("rec-art-4", f"{EU_PREFIX}Art. 4"),
    _record("rec-evaluator-fails", "ISO_IEC_27090:6.9"),
    _record("rec-evaluator-silent", "ISO_IEC_27090:6.8"),
    _record(
        "rec-mixed-not-applicable",
        "ISO_IEC_42001:Clause 6.1.2",
        kind="not_applicable",
        statement="Not an AI provider.",
    ),
]

# (case, requirement id) in the catalogue's spelling (the EU AI Act's ids are prefixed).
ROWS: list[tuple[str, str]] = [
    ("active", f"{ISO_27001}:A.6.3"),
    ("last-good-day", A + "3"),
    ("expired-before-issue", A + "2"),
    ("expired-after-issue", A + "4"),
    ("draft", A + "1"),
    ("revoked", A + "5"),
    ("not-applicable", "SOC_2:CC1.1"),
    ("system-record-beats-organisation", A + "6"),
    ("draft-does-not-hide-active", A + "7"),
    ("other-systems-record", A + "8"),
    ("system-record-only", A + "9"),
    ("no-record", A + "10"),
    ("eu-art-4", f"{EU_PREFIX}Art. 4"),
    ("mixed-evaluator-fails", "ISO_IEC_27090:6.9"),
    ("mixed-evaluator-silent", "ISO_IEC_27090:6.8"),
    ("mixed-not-applicable", "ISO_IEC_42001:Clause 6.1.2"),
    ("mixed-artifact-no-record", "ISO_IEC_42001:A.8.2"),
    ("mixed-eu-article", f"{EU_PREFIX}Art. 9"),
]


def _engine_id(requirement_id: str) -> str:
    """The id the engine and a bundle use: EU AI Act articles have no prefix."""
    return requirement_id.removeprefix(EU_PREFIX)


def _in_date(record: dict[str, Any], on: date) -> bool:
    until = record["valid_until"]
    return until is None or date.fromisoformat(until) >= on


def issue_bundle() -> dict[str, Any]:
    """The bundle issued on ISSUED_ON for SYSTEM: per requirement the active record in date that
    day, a system record before an organisation one. Drafts, revoked records and other systems'
    records never reach it. The key id and signature are placeholders: the CLI copies them."""
    attestations: dict[str, dict[str, Any]] = {}
    excluded: dict[str, dict[str, str]] = {}
    for rid in sorted({r["requirement_id"] for r in RECORDS}):
        shipped = [
            r
            for r in RECORDS
            if r["requirement_id"] == rid
            and r["status"] == "active"
            and r["system_id"] in (None, SYSTEM)
            and _in_date(r, ISSUED_ON)
        ]
        if not shipped:
            continue
        best = max(shipped, key=lambda r: r["system_id"] is not None)
        framework, key = framework_of(rid), _engine_id(rid)
        if best["kind"] == "not_applicable":
            excluded.setdefault(framework, {})[key] = best["statement"]
            continue
        entry: dict[str, Any] = {
            "statement": best["statement"],
            "attested_by": best["attested_by"],
            "attested_at": best["attested_at"],
            "record_id": best["id"],
        }
        if best["valid_until"]:
            entry["valid_until"] = best["valid_until"]
        attestations.setdefault(framework, {})[key] = entry
    return {
        "schema_version": "attestation_bundle/v1",
        "system_id": SYSTEM,
        "issued_at": f"{ISSUED_ON.isoformat()}T09:30:00+00:00",
        "attestations": attestations,
        "excluded": excluded,
        "key_id": "golden-key",
        "signature": "AAAA",
    }


def _eval_report() -> EvalReport:
    """EVAL_ADVERSARIAL_V1 fails and EVAL_SAFETY_LEXICAL_V1 passes; no result for
    EVAL_DATA_LEAKAGE_V1."""

    def result(evaluator_id: str, outcome: EvaluatorOutcome) -> EvaluatorResult:
        return EvaluatorResult(
            evaluator_id=evaluator_id,
            category=EvaluatorCategory.ADVERSARIAL,
            outcome=outcome,
            score=0.0 if outcome is EvaluatorOutcome.FAIL else 1.0,
            threshold=0.5,
            metric_name="golden",
            sample_count=1,
            reference="golden",
            evidence_hash="0" * 64,
        )

    return EvalReport(
        system_id=SYSTEM,
        commit_ref="0" * 40,
        eval_set_id="attestation-golden",
        eval_set_version="1",
        threshold_policy_hash="0" * 64,
        results=[
            result("EVAL_ADVERSARIAL_V1", EvaluatorOutcome.FAIL),
            result("EVAL_SAFETY_LEXICAL_V1", EvaluatorOutcome.PASS),
        ],
        evaluators_run=2,
        evaluators_failed=1,
        evaluators_skipped=0,
        overall_outcome=EvaluatorOutcome.FAIL,
        generated_at=f"{TODAY.isoformat()}T00:00:00+00:00",
    )


def _native_packs() -> list[str]:
    return [fw for fw, pack in FRAMEWORKS.items() if pack.requirements is not None]


def _engine_statuses(bundle: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Engine id -> (status, evidence_ref) for every row of the run; an excluded row has the
    status "excluded" and no reference."""
    manifest = SystemManifest(system_id=SYSTEM, intended_purpose="attestation golden")
    targets = _native_packs()
    merged, _warnings, _ref = merge_into_manifest(
        manifest, AttestationBundle.model_validate(bundle), targets
    )
    reports = evaluate_targets(
        merged,
        targets,
        commit_ref="0" * 40,
        eval_report=_eval_report(),
        today=TODAY,
    )
    out: dict[str, tuple[str, str]] = {}
    for framework_report in reports.values():
        for row in framework_report.report.articles:
            out[row.article] = (row.status.value, row.evidence_ref)
        for rid in framework_report.excluded:
            out[rid] = ("excluded", "")
    return out


def _record_id(evidence_ref: str) -> str | None:
    """The record id an attestation-decided row cites (`attestation:<name>@<date>#<id>`)."""
    if not evidence_ref.startswith("attestation:"):
        return None
    return evidence_ref.partition("#")[2] or None


def build() -> dict[str, Any]:
    bundle = issue_bundle()
    engine = _engine_statuses(bundle)
    only = {fw: sorted(attestation_only_ids(fw)) for fw in _native_packs()}
    mixed = {
        fw: sorted(attestable_ids(fw) - attestation_only_ids(fw))
        for fw in _native_packs()
        if attestable_ids(fw) - attestation_only_ids(fw)
    }
    rows = []
    for case, requirement_id in ROWS:
        engine_id = _engine_id(requirement_id)
        status, evidence_ref = engine[engine_id]
        rows.append(
            {
                "case": case,
                "requirement_id": requirement_id,
                "framework": framework_of(requirement_id),
                "bundle_id": engine_id,
                "attestation_only": engine_id in only[framework_of(requirement_id)],
                "engine_status": status,
                "engine_record_id": _record_id(evidence_ref),
            }
        )
    return {
        "_meta": {
            "description": (
                "Statuses the engine gives a fixed set of recorded attestations, and the "
                "requirement ids only an attestation can decide. Generated; do not edit."
            ),
            "regenerate": "python scripts/generate_attestation_golden.py",
            "bundle": (
                "the bundle an issuer ships for the system on bundle_issued_on; key_id and "
                "signature are placeholders (the CLI copies them without checking)"
            ),
            "ids": (
                "requirement_id is the catalogue spelling (EU AI Act articles prefixed with "
                "EU_AI_ACT:); bundle_id and the id lists use the engine's spelling"
            ),
        },
        "today": TODAY.isoformat(),
        "bundle_issued_on": ISSUED_ON.isoformat(),
        "system_id": SYSTEM,
        "attestation_only": {
            EU_AI_ACT: sorted(attestation_only_ids(EU_AI_ACT)),
            **only,
        },
        "mixed_attestable": mixed,
        "records": RECORDS,
        "bundle": bundle,
        "rows": rows,
    }


def render() -> str:
    return json.dumps(build(), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when the committed file is stale; write nothing.",
    )
    args = parser.parse_args(argv)
    text = render()
    if args.check:
        current = (
            OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.is_file() else ""
        )
        if current != text:
            print(
                f"{OUTPUT_PATH} is stale: run python scripts/generate_attestation_golden.py"
            )
            return 1
        print(f"{OUTPUT_PATH} is up to date")
        return 0
    OUTPUT_PATH.write_text(text, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
