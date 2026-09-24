"""Framework pack registry: assess one system against several frameworks.

A pack is either native (a requirements map evaluated by `build_gap_report`)
or derived (a function re-projecting the EU AI Act gap report). The EU AI Act
report is always built first, exactly as `opencomplai gaps` builds it: it is
the evidence base for derived packs and the legacy `gap_report`.

Requirement ids other than the EU AI Act's are prefixed "<FW>:<id>", so the
framework of any row or control is read from its id. See
docs/adr/ADR-framework-packs.md.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from opencomplai_core.gap_report import build_gap_report
from opencomplai_core.models import (
    CorroborationReport,
    EvalReport,
    FrameworkInputs,
    FrameworkReport,
    GapReport,
    GapStatus,
    RiskResult,
    SystemManifest,
)
from opencomplai_core.nist_rmf_report import nist_rmf_as_gap_report

_DATA_DIR = Path(__file__).resolve().parent / "data"

EU_AI_ACT = "EU_AI_ACT"


@dataclass(frozen=True)
class FrameworkPack:
    id: str
    label: str
    disclaimer_ref: str = "DISCLAIMER_V2"
    # Exactly one of `requirements` (native) and `derive` (derived) is set.
    requirements: Path | None = None
    derive: Callable[[GapReport], GapReport] | None = None
    # Data a derived pack reads besides its requirements map, for data_version.
    data_files: tuple[Path, ...] = ()


FRAMEWORKS: dict[str, FrameworkPack] = {
    EU_AI_ACT: FrameworkPack(
        EU_AI_ACT,
        "EU AI Act (Regulation (EU) 2024/1689)",
        "DISCLAIMER_V1",
        requirements=_DATA_DIR / "gap_article_map.json",
    ),
    "NIST_AI_RMF": FrameworkPack(
        "NIST_AI_RMF",
        "NIST AI RMF 1.0 (derived from EU AI Act evidence)",
        derive=nist_rmf_as_gap_report,
        data_files=(
            _DATA_DIR / "framework_crosswalk.json",
            _DATA_DIR / "nist_ai_rmf_subcategories.json",
        ),
    ),
}

_FAIL_ON: dict[str, frozenset[GapStatus]] = {
    "missing": frozenset({GapStatus.MISSING}),
    "partial": frozenset({GapStatus.MISSING, GapStatus.PARTIAL}),
}


def framework_of(requirement_id: str) -> str:
    """Framework key of a requirement id; unprefixed ids are the EU AI Act's."""
    framework, sep, _ = requirement_id.partition(":")
    return framework if sep else EU_AI_ACT


def _require_known(frameworks: Sequence[str], what: str) -> None:
    unknown = [fw for fw in frameworks if fw not in FRAMEWORKS]
    if unknown:
        raise ValueError(
            f"unknown {what} {', '.join(unknown)}; known frameworks: "
            f"{', '.join(FRAMEWORKS)}"
        )


def resolve_targets(
    manifest: SystemManifest, cli_targets: Sequence[str] | None = None
) -> list[str]:
    """Frameworks to assess, in order and without duplicates.

    CLI targets replace the manifest's; otherwise `compliance_targets`, else
    the single `compliance_target`.
    """
    targets = (
        cli_targets or manifest.compliance_targets or [str(manifest.compliance_target)]
    )
    _require_known(targets, "compliance target")
    return list(dict.fromkeys(targets))


@cache
def load_requirements_map(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def data_version(pack: FrameworkPack) -> str:
    """Short hash of the pack's data, independent of line endings and key order."""
    paths = ([pack.requirements] if pack.requirements else []) + list(pack.data_files)
    parsed = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    blob = json.dumps(parsed, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def evaluate_targets(
    manifest: SystemManifest,
    targets: Sequence[str],
    *,
    commit_ref: str,
    risk_result: RiskResult | None = None,
    corroboration_report: CorroborationReport | None = None,
    eval_report: EvalReport | None = None,
    repo_root: Path | None = None,
) -> dict[str, FrameworkReport]:
    """One FrameworkReport per framework, the EU AI Act's always first.

    The EU AI Act entry is present even when it is not a target, because its
    report is the legacy `gap_report`. Other entries follow in target order;
    rows the manifest excludes move from `report.articles` to `excluded`.
    Raises ValueError on an unknown framework, EU AI Act framework_inputs,
    an excluded/attested id the framework does not have, or a blank
    exclusion justification.
    """
    _require_known(targets, "compliance target")
    _require_known(list(manifest.framework_inputs), "framework in framework_inputs")
    if EU_AI_ACT in manifest.framework_inputs:
        raise ValueError(
            "framework_inputs.EU_AI_ACT is not supported: EU AI Act exclusions and "
            "attestations are not part of the EU gap report"
        )

    eu = build_gap_report(
        system_id=manifest.system_id,
        commit_ref=commit_ref,
        risk_result=risk_result,
        corroboration_report=corroboration_report,
        eval_report=eval_report,
        repo_root=repo_root,
    )
    eu_pack = FRAMEWORKS[EU_AI_ACT]
    reports = {
        EU_AI_ACT: FrameworkReport(
            framework=EU_AI_ACT,
            label=eu_pack.label,
            data_version=data_version(eu_pack),
            disclaimer_ref=eu_pack.disclaimer_ref,
            report=eu,
        )
    }

    for fw in dict.fromkeys(targets):
        if fw == EU_AI_ACT:
            continue
        pack = FRAMEWORKS[fw]
        inputs = manifest.framework_inputs.get(fw, FrameworkInputs())
        if pack.derive is not None:
            report = pack.derive(eu)
            attestable: set[str] = set()
        else:
            requirements = load_requirements_map(pack.requirements)
            report = build_gap_report(
                system_id=manifest.system_id,
                commit_ref=commit_ref,
                risk_result=risk_result,
                corroboration_report=corroboration_report,
                eval_report=eval_report,
                repo_root=repo_root,
                requirements=requirements,
                attestations=inputs.attested,
            )
            attestable = {
                rid
                for rid, config in requirements.items()
                if any(s["kind"] == "attestation" for s in config.get("sources", []))
            }

        ids = {row.article for row in report.articles}
        for rid, reason in inputs.excluded.items():
            if rid not in ids:
                raise ValueError(
                    f"framework_inputs.{fw}.excluded: {rid!r} is not a {fw} requirement"
                )
            if not reason.strip():
                raise ValueError(
                    f"framework_inputs.{fw}.excluded: {rid!r} needs a justification"
                )
        for rid in inputs.attested:
            if rid not in attestable:
                raise ValueError(
                    f"framework_inputs.{fw}.attested: {rid!r} is not a {fw} "
                    "requirement that takes an attestation"
                )

        kept = [
            row.model_copy(update={"disclaimer_ref": pack.disclaimer_ref})
            for row in report.articles
            if row.article not in inputs.excluded
        ]
        reports[fw] = FrameworkReport(
            framework=fw,
            label=pack.label,
            data_version=data_version(pack),
            derived_from=EU_AI_ACT if pack.derive is not None else None,
            disclaimer_ref=pack.disclaimer_ref,
            excluded={
                row.article: inputs.excluded[row.article]
                for row in report.articles
                if row.article in inputs.excluded
            },
            report=report.model_copy(update={"articles": kept}),
        )
    return reports


def validate_gate(
    frameworks: Sequence[str], fail_on: str, targets: Sequence[str]
) -> None:
    """Raise ValueError unless fail_on is valid and every gated framework is a
    known target other than the EU AI Act."""
    if fail_on not in _FAIL_ON:
        raise ValueError(
            f"fail_on must be one of {', '.join(_FAIL_ON)}, not {fail_on!r}"
        )
    if EU_AI_ACT in frameworks:
        raise ValueError("EU_AI_ACT cannot be gated: its controls already gate")
    not_targets = [fw for fw in frameworks if fw not in targets]
    _require_known(not_targets, "gated framework")
    if not_targets:
        raise ValueError(
            f"gated framework(s) not among the compliance targets: "
            f"{', '.join(not_targets)}"
        )


def gate_failures(
    reports: dict[str, FrameworkReport], frameworks: Sequence[str], fail_on: str
) -> list[str]:
    """Ids of gated rows that fail, in report order.

    A row fails when it is Missing, or Missing/Partial with fail_on "partial".
    Excluded rows are no longer in the report, and Unverified/Met never fail.
    """
    validate_gate(frameworks, fail_on, list(reports))
    failing = _FAIL_ON[fail_on]
    return [
        row.article
        for fw, framework_report in reports.items()
        if fw in frameworks
        for row in framework_report.report.articles
        if row.status in failing
    ]
