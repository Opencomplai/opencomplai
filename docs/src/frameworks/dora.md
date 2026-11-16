# DORA

This page covers `DORA`, a pack of 37 requirements drawn from Regulation (EU) 2022/2554 on digital operational resilience for the financial sector. The pack prepares evidence and reports what a repository shows. Nothing here is an audit, a certification or a legal assessment.

## What it is

A native pack. Each row carries the article and paragraph as published, a short title and a note in this project's own wording (each note starts `Evidence that`), and links to other frameworks that are the project's own judgement. The text of the Regulation is not reproduced. Every row is at low confidence and reads `mapping not yet reviewed`.

## Does it apply to you

The pack asks five questions in the manifest under `framework_inputs.DORA`: whether you are a financial entity of a type listed in Art. 2(1), whether you supply ICT services to financial entities, whether Art. 2(3) leaves you out, whether the simplified framework of Art. 16 applies, and whether the authority has identified you for threat-led testing. A financial entity reads applies. An ICT provider to financial entities reads voluntary, because customers pass Art. 28 to 30 contract terms on to it. Any other answer reads not applicable. With the simplified framework, Art. 16 is in scope and the full-framework rows it replaces are excluded. Confirm with your adviser.

## How rows are decided

Every row takes a provider attestation. 24 of 37 requirements checked from evidence as well: files and conventions in the repository corroborate the attestation. 13 of 37 are attestation only. The target is 11 of 37; the pack is above it. A scaffold left unfilled does not count as evidence. A row reads Met, Partial, Missing or Unverified.

| Evidence class | Rows |
|---|---|
| Machine | 0 |
| Hybrid | 24 |
| Organisational | 13 |

## Requirements

<!-- rows:start -->
| Requirement | Title | Evidence class | Sources | TTL days | Review |
| --- | --- | --- | --- | --- | --- |
| DORA:Art. 5(1)-(2) | Governance and organisation: management body accountability | organisational | attestation: DORA:Art. 5(1)-(2) | 365 | mapping not yet reviewed |
| DORA:Art. 5(3) | Governance and organisation: ICT third-party oversight role | organisational | attestation: DORA:Art. 5(3) | 365 | mapping not yet reviewed |
| DORA:Art. 5(4) | Governance and organisation: management body ICT knowledge | organisational | attestation: DORA:Art. 5(4) | 365 | mapping not yet reviewed |
| DORA:Art. 6(1)-(3) | ICT risk management framework: framework and asset protection | hybrid | attestation: DORA:Art. 6(1)-(3); artifact: policy_information_security (corroborating); artifact: risk_register (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 6(4) | ICT risk management framework: control function and independence | organisational | attestation: DORA:Art. 6(4) | 365 | mapping not yet reviewed |
| DORA:Art. 6(5) | ICT risk management framework: documentation and review | hybrid | attestation: DORA:Art. 6(5); artifact: management_review_minutes (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 6(6)-(7) | ICT risk management framework: internal audit and follow-up | hybrid | attestation: DORA:Art. 6(6)-(7); artifact: internal_audit_report (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 6(8) | ICT risk management framework: digital operational resilience strategy | organisational | attestation: DORA:Art. 6(8) | 365 | mapping not yet reviewed |
| DORA:Art. 7 | ICT systems, protocols and tools | organisational | attestation: DORA:Art. 7 | 365 | mapping not yet reviewed |
| DORA:Art. 8 | Identification | organisational | attestation: DORA:Art. 8 | 365 | mapping not yet reviewed |
| DORA:Art. 9 | Protection and prevention | hybrid | attestation: DORA:Art. 9; artifact: policy_access_control (corroborating); artifact: policy_cryptography (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 10 | Detection | hybrid | attestation: DORA:Art. 10; artifact: event_log_evidence (corroborating) | 90 | mapping not yet reviewed |
| DORA:Art. 11 | Response and recovery | hybrid | attestation: DORA:Art. 11; artifact: continuity_plan (corroborating); artifact: incident_response_plan (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 12 | Backup policies and procedures, restoration and recovery procedures and methods | hybrid | attestation: DORA:Art. 12; artifact: policy_backup (corroborating); artifact: restore_test_report (corroborating) | 180 | mapping not yet reviewed |
| DORA:Art. 13 | Learning and evolving | hybrid | attestation: DORA:Art. 13; artifact: corrective_action_log (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 14 | Communication | hybrid | attestation: DORA:Art. 14; artifact: incident_notification_template (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 16 | Simplified ICT risk management framework | organisational | attestation: DORA:Art. 16 | 730 | mapping not yet reviewed |
| DORA:Art. 17 | ICT-related incident management process | hybrid | attestation: DORA:Art. 17; artifact: incident_response_plan (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 18 | Classification of ICT-related incidents and cyber threats | hybrid | attestation: DORA:Art. 18; artifact: dora.incident_report#classification (corroborating) | 90 | mapping not yet reviewed |
| DORA:Art. 19(1), (4) | Reporting of major ICT-related incidents to authorities | hybrid | attestation: DORA:Art. 19(1), (4); artifact: dora.incident_report#initial-notification (corroborating) | 90 | mapping not yet reviewed |
| DORA:Art. 19(3) | Informing clients of major ICT-related incidents | hybrid | attestation: DORA:Art. 19(3); artifact: dora.incident_report#client-information (corroborating) | 90 | mapping not yet reviewed |
| DORA:Art. 24 | General requirements for digital operational resilience testing | hybrid | attestation: DORA:Art. 24; artifact: ai_red_team_report (corroborating); artifact: ci_test_workflow (corroborating) | 180 | mapping not yet reviewed |
| DORA:Art. 25 | Testing of ICT tools and systems | hybrid | attestation: DORA:Art. 25; artifact: ai_red_team_report (corroborating); artifact: sast_config (corroborating) | 180 | mapping not yet reviewed |
| DORA:Art. 26 | Advanced testing of ICT tools, systems and processes based on TLPT | organisational | attestation: DORA:Art. 26 | 730 | mapping not yet reviewed |
| DORA:Art. 27 | Requirements for testers for the carrying out of TLPT | organisational | attestation: DORA:Art. 27 | 730 | mapping not yet reviewed |
| DORA:Art. 28(1) | General principles: ICT third-party risk inside the framework | organisational | attestation: DORA:Art. 28(1) | 365 | mapping not yet reviewed |
| DORA:Art. 28(2) | General principles: strategy on ICT third-party risk | hybrid | attestation: DORA:Art. 28(2); artifact: policy_supplier (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 28(3) | General principles: register of information | hybrid | attestation: DORA:Art. 28(3); artifact: dora.register_of_information (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 28(4) | General principles: assessment before contracting | hybrid | attestation: DORA:Art. 28(4); artifact: vendor_register (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 28(5) | General principles: provider information security standards | hybrid | attestation: DORA:Art. 28(5); artifact: contract_checklist (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 28(6) | General principles: audit and inspection rights | hybrid | attestation: DORA:Art. 28(6); artifact: contract_checklist (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 28(7) | General principles: termination rights | hybrid | attestation: DORA:Art. 28(7); artifact: contract_checklist (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 28(8) | General principles: exit strategies | hybrid | attestation: DORA:Art. 28(8); artifact: exit_plan (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 29 | Preliminary assessment of ICT concentration risk at entity level | organisational | attestation: DORA:Art. 29 | 365 | mapping not yet reviewed |
| DORA:Art. 30(1)-(2) | Key contractual provisions: written contract and core terms | hybrid | attestation: DORA:Art. 30(1)-(2); artifact: contract_checklist (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 30(3) | Key contractual provisions: critical or important functions | hybrid | attestation: DORA:Art. 30(3); artifact: contract_checklist (corroborating) | 365 | mapping not yet reviewed |
| DORA:Art. 45 | Information-sharing arrangements on cyber threat information and intelligence | organisational | attestation: DORA:Art. 45 | 365 | mapping not yet reviewed |
<!-- rows:end -->

## Scaffolds

Two starting documents are written into the repository on request: a register of information on ICT third-party arrangements (`docs/ict/register-of-information.md`) and a major-incident classification and report outline (`docs/incidents/major-incident-report.md`). They have `_fill in_` placeholders. Three record templates help with ICT risk measures, incident reporting and third-party arrangements. They are drafts, not legal advice.

## Timeline

All four entries are marked `mapping not yet reviewed`.

| Entry | Period |
|---|---|
| DORA applies, Art. 64 | From 17 January 2025 |
| Major incident: initial notification, Delegated Regulation (EU) 2025/301, Art. 5(1)(a) | As early as possible, within four hours of classifying the incident as major and no later than 24 hours from awareness |
| Major incident: intermediate report, Art. 5(1)(b) | Within 72 hours of the initial notification, then updates without undue delay |
| Major incident: final report | No later than one month after the intermediate report |

## Gate in CI

```sh
opencomplai check --target DORA --gate DORA --gate-fail-on missing --repo-root .
```

The command exits 1 and lists the requirement ids when a row at the chosen level is found.

## What stays attested and why

13 rows have no evidence a tool can read, and only a person can vouch for them. They are the rows about management and judgement: management body accountability and strategy (Art. 5, Art. 6(4), Art. 6(8)), roles and responsibilities (Art. 7, Art. 8), the simplified framework (Art. 16), threat-led testing and tester duties (Art. 26, Art. 27), the third-party strategy and concentration risk (Art. 28(1), Art. 29) and the competent-authority cooperation rule (Art. 45).

## Review status

Every row is flagged `mapping not yet reviewed`. No flag has been cleared.

## Disclaimer

Evidence found gives Met, Partial or Missing, not a legal conclusion. This pack is not an audit, a certification or legal advice; the competent authority decides, and a qualified adviser can tell you about your own duties.
