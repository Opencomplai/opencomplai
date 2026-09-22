# Annex IV coverage ledger

`opencomplai docs generate` writes an Annex IV technical documentation dossier
(Article 11). This page is the honesty ledger for that dossier: for every
point, what Opencomplai actually derives today, what still requires a human
to type it in, and what is only wired evidence when the right sidecar report
exists on disk.

**Read this before you show a dossier to an auditor.** Opencomplai never
certifies compliance. It assembles structured evidence and clearly labels the
parts nobody has attested to yet. A dossier with placeholders in it is not a
complete Annex IV file, and `annex_iv_complete` says so explicitly (see
below).

## The three coverage categories

| Category | Meaning |
|---|---|
| **Automated** | Derived from the system manifest and/or the deterministic risk/rule engine, with no provider input beyond filling in the manifest. |
| **Wired evidence** | Populated only when a scan or eval sidecar report (`scan-report.json` / `eval-report.json`) is present on disk at generation time. Absent report → field stays empty. Nothing is fabricated to fill the gap. |
| **Provider attestation** | A human-authored statement Opencomplai cannot derive from the repository. Emitted as an explicit `PROVIDER_SUPPLIED_PLACEHOLDER` string when the manifest doesn't supply it — never silently blank, never invented boilerplate (DOSS-HONEST). |

## Coverage table

| # | Annex IV point | Category | What's covered today |
|---|---|---|---|
| 1 | General description (Section 1) | Automated + CLI input | `system_name`, `system_version`, `intended_purpose`, `compliance_target`, `risk_class` come from the manifest and the risk engine's classification. `provider_name` is a CLI flag (`--provider-name`) copied verbatim — not derived, not attested via the manifest. `deployment_context` is currently a fixed string (`"production"`), not derived from any real deployment signal. |
| 2 | Elements & development process (Section 2) | Automated (manifest) | `training_data_description` and `model_architecture` come from the manifest; `performance_metrics` merges manifest values with `eval_<category>_score` entries from a loaded eval sidecar. When the manifest leaves either required field blank, the dossier falls back to the literal stub `"Not specified in this release."` — not the `PROVIDER_SUPPLIED_PLACEHOLDER` marker used elsewhere — and `section2_complete` is set to `false` for HIGH-risk systems. **`section2_complete` is informational only: `validate_dossier_schema` (the CI release gate) does not check it.** |
| 3 | Monitoring, functioning and control (Section 3) | Provider attestation | `human_oversight_measures`, `monitoring_approach`, `incident_response_procedure` — all three manifest fields. `provider_supplied` is `true` only when **all three** are non-empty; a partially-filled section still counts as a placeholder for HIGH-risk gating (DOSS-HONEST: no more fabricated boilerplate here). |
| 4 | Appropriateness of performance metrics (Section 4) | Wired evidence + provider attestation | `metrics_reported` is the same manifest+eval-merged dict as Section 2 (wired evidence when `eval-report.json` is present). `appropriateness_rationale` is the manifest field `metrics_appropriateness_rationale` — a provider attestation, placeholder when absent. |
| 5 | Risk management system (Section 5) | Automated + wired evidence | `risk_assessment_id`, `risk_level`, `rules_evaluated/passed/failed`, `failed_rule_ids`, `rationale_hash` are automated output of the deterministic rule engine. `eval_set_version`, `eval_overall_outcome`, `eval_evidence_hashes` are wired evidence, populated only when `eval-report.json` is loaded. `scanner_version`, `corroboration_detected_categories`, `corroboration_discrepancies`, `corroboration_severity`, `corroboration_baseline_ref`, `corroboration_report_hash` are wired evidence, populated only when `scan-report.json` is loaded. `corroboration_review_status` is always `null` in this generator — no code path sets it yet. |
| 6 | Relevant lifecycle changes (Section 6) | Provider attestation | `lifecycle_changes` (list) and/or `change_log_reference` — manifest fields. Placeholder when both are empty. |
| 7 | Harmonised standards / alternative solutions (Section 7) | Provider attestation | `harmonised_standards` (list) and/or `alternative_solutions` — manifest fields. Placeholder when both are empty. |
| 8 | EU declaration of conformity (Section 8) | Provider attestation | `eu_declaration_of_conformity_ref` — a **reference** to the declaration, not a copy of it (Annex IV point 8 technically asks for the document itself; this engine records a pointer). `eu_declaration_of_conformity_sha256` — the SHA-256 of that signed document as uploaded to the evidence vault, letting a verifier check the referenced file without the file being embedded in the dossier JSON (see below). Both placeholder when the reference is absent. |
| 9 | Post-market monitoring plan (Section 9) | Provider attestation | `post_market_monitoring_plan_ref` and/or `post_market_monitoring_summary` — manifest fields. Placeholder when both are empty. |
| 10 | Article 12 record-keeping | Automated (partially fixed) | `log_retention_days` is configurable via `LOG_RETENTION_DAYS` (default `2555`, 7 years). `ledger_root_hash` reflects the real evidence-vault Merkle root in service-backed mode, or `null` otherwise. **`logging_enabled` and `evidence_vault_enabled` are currently emitted as fixed `true` values on every dossier** — they are not derived from whether a vault is actually configured or reachable at generation time. Treat these two booleans as "the feature exists in this build," not as a live status check of your deployment. |

Sections 6–9 plus Section 3's `monitoring_approach`/`incident_response_procedure`
plus Section 4's `appropriateness_rationale` are the eight manifest fields a
provider has to fill in by hand for a dossier to stop showing placeholders:
`human_oversight_measures` + `monitoring_approach` + `incident_response_procedure`
(Section 3), `metrics_appropriateness_rationale` (Section 4),
`lifecycle_changes` + `change_log_reference` (Section 6), `harmonised_standards`
+ `alternative_solutions` (Section 7), `eu_declaration_of_conformity_ref`
(Section 8), `post_market_monitoring_plan_ref` + `post_market_monitoring_summary`
(Section 9).

## `annex_iv_complete` — what it actually gates

`annex_iv_complete` is `true` unconditionally for non-HIGH-risk systems. For a
**HIGH-risk** system it is `true` only when Section 3 is `provider_supplied`
**and** Sections 6, 7, 8, 9 are all `provider_supplied`. It does **not**
factor in `section2_complete` — Section 2 stub content is flagged separately
and is not part of this gate.

`validate_dossier_schema` — the function the CI release gate calls — enforces,
for a HIGH-risk system only:

- Sections 6–9 are all `provider_supplied`
- `annex_iv_complete` is `true`
- Section 4 is `provider_supplied`
- Section 3 is `provider_supplied`

A HIGH-risk dossier that still carries any placeholder in those sections
**fails the release gate**. A non-HIGH-risk dossier passes with placeholders
present — the gate is deliberately scoped to where the regulation's stakes are
highest, not to every dossier ever generated.

## Why Section 8 references the declaration instead of embedding it

The signed EU declaration of conformity is a provider-issued legal document,
not something this engine generates. When a provider uploads it as evidence,
the file itself goes to the evidence vault and Section 8 records only
`eu_declaration_of_conformity_ref` (where to find it) and
`eu_declaration_of_conformity_sha256` (the uploaded file's hash) — never the
document's bytes. This keeps the dossier JSON small and diffable, avoids
duplicating a legal document across every dossier generated for the same
release, and still lets a verifier confirm the referenced file is the exact
one this dossier was generated against by recomputing its hash. See
[Evidence](evidence.md) for how the vault stores and hashes uploaded evidence.

## Why sidecar loading matters

`opencomplai docs generate` reads `scan-report.json` and `eval-report.json`
from the current directory by default (override with `--scan-report` /
`--eval-report`). These are written by `opencomplai check` and `opencomplai
gaps` (D10). If neither file exists, Section 5's scanner and eval fields stay
exactly as empty as they are in this table — generation still succeeds, it
just doesn't fabricate evidence that was never collected. See
[docs generate](../cli/docs-generate.md) and [check](../cli/check.md).

## See also

- [Evidence](evidence.md) — how evidence objects and hashes are stored and referenced.
- [Controls lifecycle](controls.md) — the persistent control register this ledger's automated fields feed into via `opencomplai gaps`/`check`.
- [Risk levels](risk-levels.md) — how `risk_class` is computed.
