# Control Codes → Principles → Articles

This page maps every EU AI Act article Opencomplai tracks to the 6 EU Trustworthy AI
principles (per the EU High-Level Expert Group on AI), and to the rule/obligation/scan/
evaluator source that produces its `opencomplai gaps` status.

**This page is generated** from `packages/core/src/opencomplai_core/data/eu_ai_act_principles.json` and `packages/core/src/opencomplai_core/data/gap_article_map.json` — the exact same data `opencomplai gaps`'s `principle_summary` output reads, so this page and the CLI can
never drift out of sync. Regenerate with `python scripts/generate_principle_docs.py`
after editing either data file.

---

## Technical Robustness and Safety

`technical_robustness_safety`

| Article | Source(s) |
|---|---|
| Art. 15 | `evaluator:EVAL_SAFETY_LEXICAL_V1`, `evaluator:EVAL_DATA_LEAKAGE_V1`, `scan:agent_framework` (detection only, never Met), `manifest:agent_declarations`, `evaluator:EVAL_ADVERSARIAL_V1` |
| Art. 25 | `rule:EU_AIA_ART25_MODIFICATION_TRAP` |
| Art. 72 | `artifact:post_market_monitoring_plan` |

## Privacy and Data Governance

`privacy_data_governance`

| Article | Source(s) |
|---|---|
| Art. 10 | `evaluator:EVAL_BIAS_FAIRNESS_V1`, `scan:pii_dataflow` (detection only, never Met) |

## Transparency

`transparency`

| Article | Source(s) |
|---|---|
| Art. 12 | `artifact:event_log_evidence`, `manifest:record_keeping_declaration`, `manifest:agent_declarations` |
| Art. 13 | `artifact:deployer_instructions`, `manifest:instructions_for_use_fields` |
| Art. 49 | `artifact:eu_database_registration_evidence` |
| Art. 50 | `obligation:transparency`, `artifact:transparency_notice_evidence` |

## Diversity, Non-discrimination and Fairness

`diversity_non_discrimination_fairness`

| Article | Source(s) |
|---|---|
| Art. 5 | `rule:EU_AIA_ART5_UNACCEPTABLE`, `obligation:prohibited` |
| Art. 6 | `rule:EU_AIA_ART6_HIGH_RISK`, `rule:EU_AIA_ART6_PROFILING`, `scan:biometric`, `scan:scoring_profiling`, `scan:agent_framework` (detection only, never Met) |
| Art. 10 | `evaluator:EVAL_BIAS_FAIRNESS_V1`, `scan:pii_dataflow` (detection only, never Met) |

## Societal and Environmental Wellbeing

`societal_environmental_wellbeing`

| Article | Source(s) |
|---|---|
| Art. 5 | `rule:EU_AIA_ART5_UNACCEPTABLE`, `obligation:prohibited` |

## Accountability

`accountability`

| Article | Source(s) |
|---|---|
| Art. 4 | `obligation:ai_literacy` |
| Art. 9 | `artifact:risk_register`, `obligation:provider_high_risk` |
| Art. 11 | `artifact:technical_documentation_dossier` |
| Art. 14 | `artifact:human_oversight_construct`, `scan:agent_framework` (detection only, never Met), `scan:mcp_server` (detection only, never Met), `manifest:human_oversight_declaration`, `manifest:agent_declarations` |
| Art. 16 | `artifact:provider_qms_bundle` |
| Art. 17 | `artifact:provider_qms` |
| Art. 24 | `artifact:distributor_conformity` |
| Art. 26 | `artifact:deployer_use_records`, `manifest:agent_declarations` |
| Art. 43 | `artifact:conformity_assessment_docs` |
| Art. 53 | `obligation:gpai_provider`, `artifact:gpai_model_documentation`, `artifact:gpai_downstream_information` |
| Art. 55 | `obligation:gpai_systemic_risk`, `artifact:gpai_systemic_risk_evaluation` |
| Art. 73 | `artifact:serious_incident_log` |

---

See [Control Codes Reference](control-codes.md) for what triggers each rule code, and run `opencomplai gaps` to see this same mapping applied to your own system.
