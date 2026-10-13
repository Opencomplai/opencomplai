# ADR: EU AI Act Scan — Callsite-Level AI Usage Gate

**Status:** Accepted  
**Date:** 2026-06-26  
**Amended:** 2026-10 (decision 8)

## Context

`--ai-intent` previously classified every callsite in AI-adjacent files, producing thousands of
non-AI annotations (`APIRouter`, `ASGITransport`) with generic Art.50 defaults.

## Decision

1. **Primary gate:** Callsite-level filtering in `ai_usage_gate.py`, invoked once from `scan_engine.py`.
2. **File filter:** Performance pre-filter only; does not determine output membership.
3. **Fusion policy:** Only `prohibited`, `high_risk`, and `limited_risk` enter `report.evidence` and discrepancy fusion.
4. **Usage inventory:** Gated callsites (including `minimal`) populate `eu_ai_scan.capabilities` for CLI Section 1.
5. **Classification snippet:** Callsite line ±2; token-first matching before snippet.
6. **`risk_tier` enum:** `prohibited | high_risk | limited_risk | minimal`.
7. **Backward compat:** `--ai-legacy` restores ungated behavior; `DET_INTENT` version `1.1.0`.
8. **Candidate tier:** `eu_ai_scan.candidates` is a separate list of leads for a person, never findings.
   Each entry has exactly `library`, `file`, `line` (1-based) and `reason`; the only reason is
   `imported_not_classified` (an AI library is imported but yields no Annex III signal). There is no tier,
   area, severity or confidence field. A candidate never enters the gate, the classification proposal,
   severity, `regulatory_finding_count`, the report hash or any exit code. It is a separate tier because
   public pull request 100 fed such imports into the findings and intent recall fell from 75.9% to 24.1%.
   `DET_INTENT` stays `1.1.0` (candidates are produced outside the detector), `RULE_SET_VERSION` is not
   bumped, and the scan envelope `schema_version` stays `1.0` because the field is additive (whether a
   minor bump is wanted is a founder note, not decided here).

## JSON contract

`CorroborationReport.eu_ai_scan` holds structured EU AI Act findings; intent evidence in
`report.evidence` is limited to regulatory tiers when `--ai-intent` (non-legacy).
`eu_ai_scan.candidates` holds leads for a person (decision 8); it is empty when nothing qualifies.
