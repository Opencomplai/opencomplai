# NIS2: network and information security duties

This page covers `NIS2`, a pack of 21 requirements taken from Directive (EU) 2022/2555 (CELEX
32022L2555): the governance, risk-management and incident-reporting duties of Arts. 20, 21 and 23.
They are 21 rows, not the whole Directive. National transposition differs per member state; the
pack follows the Directive's text, so check your national law for the rules that bind you. Nothing
here is an audit, a certification or a legal assessment.

## What it is

A native pack. Each row is one article or paragraph, with the article number as published, a
one-line description in this project's own words, and links to other frameworks that are the
project's own judgement. Every row is at low confidence and reads `mapping not yet reviewed`.

## Does it apply to you

The pack asks four questions in the manifest under `framework_inputs.NIS2`: whether you work in a
sector listed in Annex I or II, whether you are a special-case entity in scope whatever your size,
whether you are medium-sized or larger, and whether you supply an organisation that is in scope.
A system outside the listed sectors reads not applicable, or voluntary when you supply an
in-scope customer; a medium or larger entity in a listed sector applies. National law can still
designate other entities, so confirm with your adviser.

## How rows are decided

Every row takes a provider attestation. 16 of 21 requirements are checked from evidence as well:
files and conventions in the repository (a security policy, an incident response plan, a vendor
register, an incident notification record and similar) corroborate the attestation. 5 of 21 are
attestation only. The target is 7 of 21; the pack is above it. A scaffold left unfilled does not
count as evidence. A row reads Met, Partial, Missing or Unverified.

| Evidence class | Rows |
|---|---|
| Machine | 0 |
| Hybrid | 16 |
| Organisational | 5 |

## Requirements

<!-- rows:start -->
| Requirement | Title | Evidence class | Sources | TTL days | Review |
| --- | --- | --- | --- | --- | --- |
| NIS2:Art. 20(1) | Governance: management approves and oversees the security measures | organisational | attestation: NIS2:Art. 20(1) | 365 | mapping not yet reviewed |
| NIS2:Art. 20(2) | Governance: cybersecurity training for management bodies | organisational | attestation: NIS2:Art. 20(2) | 365 | mapping not yet reviewed |
| NIS2:Art. 21(1) | Appropriate and proportionate cybersecurity risk-management measures | organisational | attestation: NIS2:Art. 21(1) | 365 | mapping not yet reviewed |
| NIS2:Art. 21(2)(a) | Policies on risk analysis and information system security | hybrid | attestation: NIS2:Art. 21(2)(a); artifact: policy_information_security (corroborating) | 365 | mapping not yet reviewed |
| NIS2:Art. 21(2)(b) | Incident handling | hybrid | attestation: NIS2:Art. 21(2)(b); artifact: incident_response_plan (corroborating) | 365 | mapping not yet reviewed |
| NIS2:Art. 21(2)(c) | Business continuity, backup, disaster recovery and crisis management | hybrid | attestation: NIS2:Art. 21(2)(c); artifact: continuity_plan (corroborating); artifact: restore_test_report (corroborating) | 180 | mapping not yet reviewed |
| NIS2:Art. 21(2)(d) | Supply chain security, including direct suppliers and service providers | hybrid | attestation: NIS2:Art. 21(2)(d); artifact: vendor_register (corroborating); artifact: policy_supplier (corroborating) | 365 | mapping not yet reviewed |
| NIS2:Art. 21(2)(e) | Security in systems acquisition, development, maintenance and vulnerabilities | hybrid | attestation: NIS2:Art. 21(2)(e); artifact: vulnerability_handling_policy (corroborating); artifact: sast_config (corroborating) | 365 | mapping not yet reviewed |
| NIS2:Art. 21(2)(f) | Assessing the effectiveness of cybersecurity risk-management measures | hybrid | attestation: NIS2:Art. 21(2)(f); artifact: internal_audit_report (corroborating) | 365 | mapping not yet reviewed |
| NIS2:Art. 21(2)(g) | Basic cyber hygiene practices and cybersecurity training | hybrid | attestation: NIS2:Art. 21(2)(g); artifact: competence_training_record (corroborating) | 365 | mapping not yet reviewed |
| NIS2:Art. 21(2)(h) | Cryptography and, where appropriate, encryption | hybrid | attestation: NIS2:Art. 21(2)(h); artifact: policy_cryptography (corroborating) | 365 | mapping not yet reviewed |
| NIS2:Art. 21(2)(i) | Human resources security, access control and asset management | hybrid | attestation: NIS2:Art. 21(2)(i); artifact: policy_access_control (corroborating) | 365 | mapping not yet reviewed |
| NIS2:Art. 21(2)(j) | Multi-factor authentication and secured communications | organisational | attestation: NIS2:Art. 21(2)(j) | 365 | mapping not yet reviewed |
| NIS2:Art. 21(3) | Supplier vulnerabilities and quality when choosing supply chain measures | hybrid | attestation: NIS2:Art. 21(3); artifact: vendor_register (corroborating) | 365 | mapping not yet reviewed |
| NIS2:Art. 21(4) | Corrective measures when the Art. 21(2) measures are not met | hybrid | attestation: NIS2:Art. 21(4); artifact: corrective_action_log (corroborating) | 365 | mapping not yet reviewed |
| NIS2:Art. 23(1) | Notifying the CSIRT or authority of significant incidents | hybrid | attestation: NIS2:Art. 23(1); artifact: incident_notification_template (corroborating) | 365 | mapping not yet reviewed |
| NIS2:Art. 23(2) | Informing service recipients of significant cyber threats | organisational | attestation: NIS2:Art. 23(2) | 365 | mapping not yet reviewed |
| NIS2:Art. 23(4)(a) | Early warning within 24 hours | hybrid | attestation: NIS2:Art. 23(4)(a); artifact: nis2.incident_notification_record#early-warning (corroborating) | 90 | mapping not yet reviewed |
| NIS2:Art. 23(4)(b) | Incident notification within 72 hours | hybrid | attestation: NIS2:Art. 23(4)(b); artifact: nis2.incident_notification_record#notification (corroborating) | 90 | mapping not yet reviewed |
| NIS2:Art. 23(4)(c) | Intermediate report on request | hybrid | attestation: NIS2:Art. 23(4)(c); artifact: nis2.incident_notification_record#intermediate-report (corroborating) | 90 | mapping not yet reviewed |
| NIS2:Art. 23(4)(d) | Final report within one month | hybrid | attestation: NIS2:Art. 23(4)(d); artifact: nis2.incident_notification_record#final-report (corroborating) | 90 | mapping not yet reviewed |
<!-- rows:end -->

## Scaffolds

Two starting documents are written into the repository on request: an information security policy
(`docs/policies/information-security.md`, Art. 21) and an incident notification record
(`docs/security/incident-notification.md`, Art. 23). Each has `_fill in_` placeholders. Two
templates help with a security measure and a staged incident report. They are drafts, not legal
advice.

## Timeline

All five entries are marked `mapping not yet reviewed`.

| Entry | Period |
|---|---|
| Member states apply their NIS2 measures, Art. 41(1) | From 18 October 2024 |
| Early warning of a significant incident, Art. 23(4)(a) | 24 hours after becoming aware |
| Incident notification of a significant incident, Art. 23(4)(b) | 72 hours after becoming aware |
| Final report on a significant incident, Art. 23(4)(d) | One month after the incident notification |
| Implementing rules for digital infrastructure and digital providers, Regulation (EU) 2024/2690, Art. 16 | From 7 November 2024 |

## Gate in CI

```sh
opencomplai check --target NIS2 --gate NIS2 --gate-fail-on missing --repo-root .
```

The command exits 1 and lists the requirement ids when a row at the chosen level is found.

## What stays attested and why

Five rows have no evidence a tool can read, and only a person can vouch for them:

- Art. 20(1), management approval and oversight: that the management body approves the measures and oversees them.
- Art. 20(2), management training: that members of the management body have been trained.
- Art. 21(1), appropriate and proportionate measures: that the measures fit the risk and the entity.
- Art. 21(2)(j), multi-factor authentication and secured communications: that they are in use where appropriate.
- Art. 23(2), informing service recipients: that recipients are told of significant cyber threats.

## Review status

Every row and every timeline entry is flagged `mapping not yet reviewed`. No flag has been cleared.
The 24-hour, 72-hour and one-month periods and the application date were read against EUR-Lex
(CELEX 32022L2555); the implementing regulation is CELEX 32024R2690.

## Disclaimer

Evidence found gives Met, Partial or Missing, not a legal conclusion. This pack is not an audit, a
certification or legal advice; ask a qualified lawyer about your own duties.
