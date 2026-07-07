# ADR: EU AI Act Scan — Callsite-Level AI Usage Gate

**Status:** Accepted  
**Date:** 2026-06-26

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

## JSON contract

`CorroborationReport.eu_ai_scan` holds structured EU AI Act findings; intent evidence in
`report.evidence` is limited to regulatory tiers when `--ai-intent` (non-legacy).
