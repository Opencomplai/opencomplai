# SOC 2 Trust Services Criteria

This page covers `SOC_2`, a pack of 61 requirements, one per criterion of the AICPA Trust Services Criteria (security, availability, confidentiality, processing integrity and privacy). The criteria are a framework for an independent assurance engagement; they create no legal duty. The pack prepares evidence for an auditor and replaces none of the auditor's work. Nothing here is an audit, a certification or a legal assessment.

## What it is

A native pack. Each row carries the criterion id as numbered by the AICPA, a title and a note in this project's own wording (each note starts `Evidence that`), and links to other frameworks that are the project's own judgement. The standard's text is not reproduced. Every row is at low confidence and reads `mapping not yet reviewed`.

## Does it apply to you

The pack asks five questions in the manifest under `framework_inputs.SOC_2`: whether customers or contracts ask for an independent assurance engagement, and whether the availability, confidentiality, processing integrity and privacy categories are part of it. A yes to the first reads applies. A no to a category takes that category out of scope. With no answers the pack reads voluntary. Confirm with your adviser.

## How rows are decided

Every row takes a provider attestation. 32 of 61 requirements checked from evidence as well: files and conventions in the repository corroborate the attestation. 29 of 61 are attestation only. The target is 17 of 61; the pack is above it. A scaffold left unfilled does not count as evidence. A row reads Met, Partial, Missing or Unverified.

| Evidence class | Rows |
|---|---|
| Machine | 0 |
| Hybrid | 32 |
| Organisational | 29 |

## Requirements

<!-- rows:start -->
| Requirement | Title | Evidence class | Sources | TTL days | Review |
| --- | --- | --- | --- | --- | --- |
| SOC_2:CC1.1 | Integrity and ethical values | organisational | attestation: SOC_2:CC1.1 | 365 | mapping not yet reviewed |
| SOC_2:CC1.2 | Board independence and oversight of internal control | organisational | attestation: SOC_2:CC1.2 | 365 | mapping not yet reviewed |
| SOC_2:CC1.3 | Structures, reporting lines and responsibilities | organisational | attestation: SOC_2:CC1.3 | 365 | mapping not yet reviewed |
| SOC_2:CC1.4 | Attracting, developing and retaining competent people | hybrid | attestation: SOC_2:CC1.4; artifact: competence_training_record (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC1.5 | Accountability for internal control duties | organisational | attestation: SOC_2:CC1.5 | 365 | mapping not yet reviewed |
| SOC_2:CC2.1 | Quality information to support internal control | hybrid | attestation: SOC_2:CC2.1; artifact: soc_2.system_description#commitments (corroborating) | 730 | mapping not yet reviewed |
| SOC_2:CC2.2 | Internal communication of objectives and duties | hybrid | attestation: SOC_2:CC2.2; artifact: policy_information_security (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC2.3 | Communication with external parties | hybrid | attestation: SOC_2:CC2.3; artifact: security_policy_file (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC3.1 | Clear objectives so risks can be assessed | hybrid | attestation: SOC_2:CC3.1; artifact: objectives_record (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC3.2 | Risk identification and analysis | hybrid | attestation: SOC_2:CC3.2; artifact: risk_register (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC3.3 | Fraud risk consideration | organisational | attestation: SOC_2:CC3.3 | 365 | mapping not yet reviewed |
| SOC_2:CC3.4 | Assessing changes that affect internal control | organisational | attestation: SOC_2:CC3.4 | 365 | mapping not yet reviewed |
| SOC_2:CC4.1 | Ongoing and separate control evaluations | hybrid | attestation: SOC_2:CC4.1; artifact: internal_audit_report (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC4.2 | Reporting and correcting control deficiencies | hybrid | attestation: SOC_2:CC4.2; artifact: corrective_action_log (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC5.1 | Control activities that reduce risk | hybrid | attestation: SOC_2:CC5.1; artifact: soc_2.control_matrix (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC5.2 | General controls over technology | organisational | attestation: SOC_2:CC5.2 | 365 | mapping not yet reviewed |
| SOC_2:CC5.3 | Controls deployed through policies and procedures | hybrid | attestation: SOC_2:CC5.3; artifact: policy_information_security (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC6.1 | Logical access security over protected assets | hybrid | attestation: SOC_2:CC6.1; artifact: policy_access_control (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC6.2 | User registration and credential issuance | organisational | attestation: SOC_2:CC6.2 | 365 | mapping not yet reviewed |
| SOC_2:CC6.3 | Granting, changing and removing access | organisational | attestation: SOC_2:CC6.3 | 365 | mapping not yet reviewed |
| SOC_2:CC6.4 | Physical access to facilities and assets | organisational | attestation: SOC_2:CC6.4 | 365 | mapping not yet reviewed |
| SOC_2:CC6.5 | Secure disposal of assets and media | organisational | attestation: SOC_2:CC6.5 | 365 | mapping not yet reviewed |
| SOC_2:CC6.6 | Protection against threats from outside the system boundary | organisational | attestation: SOC_2:CC6.6 | 365 | mapping not yet reviewed |
| SOC_2:CC6.7 | Controls over moving and transmitting information | hybrid | attestation: SOC_2:CC6.7; artifact: policy_cryptography (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC6.8 | Preventing and detecting malicious software | organisational | attestation: SOC_2:CC6.8 | 365 | mapping not yet reviewed |
| SOC_2:CC7.1 | Detecting vulnerabilities and risky configuration changes | hybrid | attestation: SOC_2:CC7.1; artifact: sast_config (corroborating); artifact: dependency_update_config (corroborating) | 90 | mapping not yet reviewed |
| SOC_2:CC7.2 | Monitoring systems for anomalies | hybrid | attestation: SOC_2:CC7.2; artifact: event_log_evidence (corroborating) | 90 | mapping not yet reviewed |
| SOC_2:CC7.3 | Evaluating security events as incidents | hybrid | attestation: SOC_2:CC7.3; artifact: incident_response_plan (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC7.4 | Incident response program | hybrid | attestation: SOC_2:CC7.4; artifact: incident_response_plan (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC7.5 | Recovery from security incidents | hybrid | attestation: SOC_2:CC7.5; artifact: restore_test_report (corroborating) | 180 | mapping not yet reviewed |
| SOC_2:CC8.1 | Change management | hybrid | attestation: SOC_2:CC8.1; artifact: policy_change_management (corroborating); artifact: code_review_rules (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC9.1 | Risk mitigation for business disruption | hybrid | attestation: SOC_2:CC9.1; artifact: continuity_plan (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:CC9.2 | Vendor and business partner risk | hybrid | attestation: SOC_2:CC9.2; artifact: vendor_register (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:A1.1 | Capacity management | organisational | attestation: SOC_2:A1.1 | 365 | mapping not yet reviewed |
| SOC_2:A1.2 | Environmental protections, backup and recovery infrastructure | hybrid | attestation: SOC_2:A1.2; artifact: policy_backup (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:A1.3 | Testing of recovery plans | hybrid | attestation: SOC_2:A1.3; artifact: restore_test_report (corroborating) | 180 | mapping not yet reviewed |
| SOC_2:C1.1 | Identifying and maintaining confidential information | organisational | attestation: SOC_2:C1.1 | 365 | mapping not yet reviewed |
| SOC_2:C1.2 | Disposal of confidential information | organisational | attestation: SOC_2:C1.2 | 365 | mapping not yet reviewed |
| SOC_2:PI1.1 | Processing objectives and information specifications | organisational | attestation: SOC_2:PI1.1 | 365 | mapping not yet reviewed |
| SOC_2:PI1.2 | Controls over system inputs | organisational | attestation: SOC_2:PI1.2 | 365 | mapping not yet reviewed |
| SOC_2:PI1.3 | Controls over system processing | organisational | attestation: SOC_2:PI1.3 | 365 | mapping not yet reviewed |
| SOC_2:PI1.4 | Controls over system outputs | organisational | attestation: SOC_2:PI1.4 | 365 | mapping not yet reviewed |
| SOC_2:PI1.5 | Controls over stored items | organisational | attestation: SOC_2:PI1.5 | 365 | mapping not yet reviewed |
| SOC_2:P1.1 | Privacy notice to data subjects | hybrid | attestation: SOC_2:P1.1; artifact: privacy_notice (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:P2.1 | Choice and consent | organisational | attestation: SOC_2:P2.1 | 365 | mapping not yet reviewed |
| SOC_2:P3.1 | Collection of personal information | hybrid | attestation: SOC_2:P3.1; artifact: record_of_processing (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:P3.2 | Explicit consent for sensitive information | organisational | attestation: SOC_2:P3.2 | 365 | mapping not yet reviewed |
| SOC_2:P4.1 | Use limited to stated purposes | hybrid | attestation: SOC_2:P4.1; artifact: record_of_processing (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:P4.2 | Retention of personal information | organisational | attestation: SOC_2:P4.2 | 365 | mapping not yet reviewed |
| SOC_2:P4.3 | Secure disposal of personal information | organisational | attestation: SOC_2:P4.3 | 365 | mapping not yet reviewed |
| SOC_2:P5.1 | Data subject access to their information | hybrid | attestation: SOC_2:P5.1; artifact: data_subject_request_procedure (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:P5.2 | Correction of personal information | hybrid | attestation: SOC_2:P5.2; artifact: data_subject_request_procedure (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:P6.1 | Disclosure to third parties with consent | organisational | attestation: SOC_2:P6.1 | 365 | mapping not yet reviewed |
| SOC_2:P6.2 | Record of authorised disclosures | organisational | attestation: SOC_2:P6.2 | 365 | mapping not yet reviewed |
| SOC_2:P6.3 | Record of unauthorised disclosures and breaches | hybrid | attestation: SOC_2:P6.3; artifact: breach_register (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:P6.4 | Privacy commitments from vendors and third parties | hybrid | attestation: SOC_2:P6.4; artifact: processor_register (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:P6.5 | Vendor duty to report unauthorised disclosures | hybrid | attestation: SOC_2:P6.5; artifact: processor_register (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:P6.6 | Breach and incident notification | hybrid | attestation: SOC_2:P6.6; artifact: breach_register (corroborating); artifact: incident_notification_template (corroborating) | 365 | mapping not yet reviewed |
| SOC_2:P6.7 | Accounting of held and disclosed information | organisational | attestation: SOC_2:P6.7 | 365 | mapping not yet reviewed |
| SOC_2:P7.1 | Accuracy and quality of personal information | organisational | attestation: SOC_2:P7.1 | 365 | mapping not yet reviewed |
| SOC_2:P8.1 | Privacy inquiries, complaints and compliance monitoring | hybrid | attestation: SOC_2:P8.1; artifact: data_subject_request_procedure (corroborating) | 365 | mapping not yet reviewed |
<!-- rows:end -->

## Scaffolds

Two starting documents are written into the repository on request: a system description (`docs/assurance/system-description.md`) and a control matrix (`docs/assurance/control-matrix.md`). They have `_fill in_` placeholders. Four record templates help with governance, security operation, availability and privacy evidence. They are drafts, not legal advice.

## Timeline

This pack has no timeline: a standard without legal application dates.

## Gate in CI

```sh
opencomplai check --target SOC_2 --gate SOC_2 --gate-fail-on missing --repo-root .
```

The command exits 1 and lists the requirement ids when a row at the chosen level is found.

## What stays attested and why

29 rows have no evidence a tool can read, and only a person can vouch for them. They are the rows about people and decisions: conduct and accountability (CC1.1, CC1.2, CC1.3, CC1.5), risk assessment judgements (CC3.3, CC3.4), policies and access decisions (CC5.2, CC6.2 to CC6.6, CC6.8), availability and confidentiality commitments (A1.1, C1.1, C1.2), processing integrity (PI1.1 to PI1.5) and privacy notice, choice and disclosure (P2.1, P3.2, P4.2, P4.3, P6.1, P6.2, P6.7, P7.1).

## Review status

Every row is flagged `mapping not yet reviewed`. No flag has been cleared.

## Disclaimer

Evidence found gives Met, Partial or Missing, not a legal conclusion. This pack is not an audit, a certification or legal advice; the auditor decides, and a qualified adviser can tell you about your own duties.
