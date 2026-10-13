# ADR: Proposal leads tier

**Status:** Accepted  
**Date:** 2026-10-13

## Context

The default scan sees nothing for EU AI Act Annex III areas 3 to 8: the token
dictionary that runs under `check --scan` and the quick scan has no signal for
education, employment, essential services, law enforcement, migration or the
administration of justice. The deterministic proposal matcher, which ships in the
optional AI plugin, does read those areas. Its output is evidence for a person to
look at, not a verdict.

This record fixes where that output lives, what it may carry and what it may
never touch. It builds on the candidate tier
described in `docs/adr/ADR-eu-ai-scan-gate.md` (decision 8 there): a separate
list next to the findings that is never a finding. See
[Annex III detection benchmark](../concepts/annex-iii-benchmark.md) for the
measurements this record pins, [`scan`](../cli/scan.md) for the report the tier
appears in and [`check`](../cli/check.md) for the gate it must not move.

## Decision

1. **A separate tier.** The tier is a list `proposal_leads` on `eu_ai_scan`, next
   to `candidates`. It is empty unless the optional AI plugin is installed and
   the matcher found something. A lead is a pointer for a person to review, never
   a finding.
2. **Entry fields, exactly.** `reason` (only `deterministic_matcher`), `file`,
   `line` (1-based), `function`, `annex_iii_area` (integer 1 to 8),
   `confidence_band` (the schema allows `low`, `medium` and `high`; this release
   produces `low` and `medium` only) and `signals` (a list of
   strings). There is no `risk_tier`, severity, obligation or rationale field, on
   purpose: a field that reads like a finding invites a reader to treat the entry
   as one. Entries are sorted by file, line, function and area.
3. **Severity none, no gate, no exit code.** A lead never changes any exit code,
   `severity`, `discrepancies`, `regulatory_finding_count`, `report_hash`, the
   classification proposal, the SARIF output or a verdict.
4. **Never in the signed artifact.** Leads do not enter `compliance-artifact.json`,
   neither in `scan_summary` nor in any new field.
5. **Where shown.** The `scan -o json` payload under `eu_ai_scan.proposal_leads`,
   and a text section rendered apart from the findings. The notice that the
   default scan has no signal for some areas is a separate decision
   (`default_scan_coverage`) and is not part of this tier.
6. **The declared purpose stays authoritative.** A lead needs a person to confirm
   it through the existing proposal and confirmation flow before it can matter. An
   unconfirmed or stale lead never changes a verdict.
7. **Plugin absent.** One install-hint line, no new hard dependency, base
   behaviour unchanged.
8. **No version bump.** `RULE_SET_VERSION` and `SCANNER_VERSION` stay as they are
   and no schema pin changes; the envelope field is additive and existing
   consumers ignore it.
9. **Benchmark pins stay.** The 46-fixture intent-path pins (precision 73.3%,
   recall 75.9%) and the default-path floors (44.4% precision, 13.8% recall) are
   untouched. Leads are measured on their own set and never folded into those
   tables. The floor for a lead is the intent-path training precision of 73.3% on
   every area other than 5; an area that stays under it is notice only. Area 5 is
   always shown at the lowest confidence.
10. **The tier's data is flagged.** The `confidence_band` and `floor` rows below
    each carry `source`, `confidence` and `needs_founder_review: true`.

## JSON contract

The hand-written schema is `schemas/proposal_leads.schema.json` in the core
package (JSON Schema draft 2020-12). It is closed: an entry with any other key is
rejected, and all seven fields are required. Publishing it next to the other
published schemas is a later decision and is marked `needs_founder_review`.

```json
{
  "proposal_leads": [
    {
      "reason": "deterministic_matcher",
      "file": "src/screening/rank.py",
      "line": 42,
      "function": "rank_candidates",
      "annex_iii_area": 4,
      "confidence_band": "medium",
      "signals": ["rank_candidates", "applicant"]
    }
  ]
}
```

Data rows (compliance content is data):

| Row | Value | source | confidence | needs_founder_review |
|-----|-------|--------|------------|----------------------|
| `confidence_band` | `low`, `medium`, `high` allowed by the schema; this release produces `low` and `medium` only: area 5 is always `low`, a matched code signal is `medium`, a keyword-only match is `low` | round decision on the leads floor, heuristic | low | true |
| `floor` | precision at or above 73.3% on areas other than 5, else notice only; area 5 always lowest confidence | round decision on the leads floor, heuristic | low | true |

## Benchmark pins

| Path | Precision | Recall | Status |
|------|-----------|--------|--------|
| Intent path (46 fixtures) | 73.3% | 75.9% | pinned, untouched |
| Default scan path | 44.4% | 13.8% | pinned, untouched |

A lead set has its own fixtures and its own table. Its precision is compared with
the 73.3% floor per area; it is never averaged into the rows above.

## Consequences

- A reader of the default scan can see where the matcher points, without a lead
  being able to fail a build or alter a signed record.
- The producer ships: the tests for the schema, the signed artifact, the ADR and
  the scan summary field all run against it.
- Because the entry has no risk tier or rationale, a lead cannot be quoted as a
  classification; turning one into a classification goes through a person.
- The band thresholds and the floor are heuristics until measured on the lead
  set. They are flagged for the founder rather than presented as settled.
