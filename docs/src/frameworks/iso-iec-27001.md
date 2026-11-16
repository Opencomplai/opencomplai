# ISO/IEC 27001

## What it is

ISO/IEC 27001:2022 is a standard for an information security management system: the clauses a
management system has to run, and the Annex A security controls. Opencomplai carries it as the native
target `ISO_IEC_27001`, with 118 requirement rows. The standard's text is not reproduced here; each row
has an id and a note in this project's own words on the evidence we look for.

## Does it apply to you

Nothing in law applies it. It is voluntary unless a customer contract, a plan to seek a certificate or an
internal policy commits you to it. Four manifest answers shape the scope: whether you are committed to
it, control premises, develop software, and have staff beyond the founders. A row that does not fit your
answers is listed as excluded, with the reason, and is not scored.

## How rows are decided

Every row has an evidence class. Of the 118 rows, 0 are machine, 43 are hybrid and 75 are organisational.
So **43 of 118 requirements are checked from evidence** (a draft estimate; target 34, floor 28). A hybrid
row reads a file or code convention in your repository and also takes an attestation. An organisational
row takes an attestation only.

Each row ends as Met, Partial, Missing or Unverified. Evidence found gives Met, Partial or Missing; a row
with no evidence and no attestation reads Unverified.

## Requirements

The table is generated from `requirements.json` by `tools/packs/pack_doc.py`. A row marked
`mapping not yet reviewed` has a mapping that no reviewer has confirmed yet.

<!-- rows:start -->
| Requirement | Title | Evidence class | Sources | TTL days | Review |
| --- | --- | --- | --- | --- | --- |
| ISO_IEC_27001:Clause 4.1 | Understanding the organization and its context | organisational | attestation: ISO_IEC_27001:Clause 4.1 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 4.2 | Understanding the needs and expectations of interested parties | organisational | attestation: ISO_IEC_27001:Clause 4.2 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 4.3 | Determining the scope of the information security management system | hybrid | attestation: ISO_IEC_27001:Clause 4.3; artifact: scope_statement (corroborating) | 730 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 4.4 | Information security management system | organisational | attestation: ISO_IEC_27001:Clause 4.4 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 5.1 | Leadership and commitment | organisational | attestation: ISO_IEC_27001:Clause 5.1 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 5.2 | Policy | hybrid | attestation: ISO_IEC_27001:Clause 5.2; artifact: policy_information_security (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 5.3 | Organizational roles, responsibilities and authorities | organisational | attestation: ISO_IEC_27001:Clause 5.3 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 6.1.1 | General | organisational | attestation: ISO_IEC_27001:Clause 6.1.1 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 6.1.2 | Information security risk assessment | hybrid | attestation: ISO_IEC_27001:Clause 6.1.2; artifact: risk_register (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 6.1.3 | Information security risk treatment | hybrid | attestation: ISO_IEC_27001:Clause 6.1.3; artifact: iso_iec_27001.risk_treatment_plan (corroborating); artifact: iso_iec_27001.soa_annex_a (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 6.2 | Information security objectives and planning to achieve them | hybrid | attestation: ISO_IEC_27001:Clause 6.2; artifact: objectives_record (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 6.3 | Planning of changes | organisational | attestation: ISO_IEC_27001:Clause 6.3 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 7.1 | Resources | organisational | attestation: ISO_IEC_27001:Clause 7.1 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 7.2 | Competence | hybrid | attestation: ISO_IEC_27001:Clause 7.2; artifact: competence_training_record (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 7.3 | Awareness | organisational | attestation: ISO_IEC_27001:Clause 7.3 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 7.4 | Communication | organisational | attestation: ISO_IEC_27001:Clause 7.4 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 7.5 | Documented information | organisational | attestation: ISO_IEC_27001:Clause 7.5 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 8.1 | Operational planning and control | organisational | attestation: ISO_IEC_27001:Clause 8.1 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 8.2 | Information security risk assessment | hybrid | attestation: ISO_IEC_27001:Clause 8.2; artifact: risk_register (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 8.3 | Information security risk treatment | hybrid | attestation: ISO_IEC_27001:Clause 8.3; artifact: iso_iec_27001.risk_treatment_plan (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 9.1 | Monitoring, measurement, analysis and evaluation | organisational | attestation: ISO_IEC_27001:Clause 9.1 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 9.2 | Internal audit | hybrid | attestation: ISO_IEC_27001:Clause 9.2; artifact: internal_audit_report (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 9.3 | Management review | hybrid | attestation: ISO_IEC_27001:Clause 9.3; artifact: management_review_minutes (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 10.1 | Continual improvement | organisational | attestation: ISO_IEC_27001:Clause 10.1 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:Clause 10.2 | Nonconformity and corrective action | hybrid | attestation: ISO_IEC_27001:Clause 10.2; artifact: corrective_action_log (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.1 | Policies for information security | hybrid | attestation: ISO_IEC_27001:A.5.1; artifact: policy_information_security (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.2 | Information security roles and responsibilities | organisational | attestation: ISO_IEC_27001:A.5.2 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.3 | Segregation of duties | organisational | attestation: ISO_IEC_27001:A.5.3 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.4 | Management responsibilities | organisational | attestation: ISO_IEC_27001:A.5.4 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.5 | Contact with authorities | organisational | attestation: ISO_IEC_27001:A.5.5 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.6 | Contact with special interest groups | organisational | attestation: ISO_IEC_27001:A.5.6 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.7 | Threat intelligence | organisational | attestation: ISO_IEC_27001:A.5.7 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.8 | Information security in project management | organisational | attestation: ISO_IEC_27001:A.5.8 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.9 | Inventory of information and other associated assets | hybrid | attestation: ISO_IEC_27001:A.5.9; artifact: iso_iec_27001.asset_inventory (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.10 | Acceptable use of information and other associated assets | hybrid | attestation: ISO_IEC_27001:A.5.10; artifact: policy_acceptable_use (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.11 | Return of assets | organisational | attestation: ISO_IEC_27001:A.5.11 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.12 | Classification of information | organisational | attestation: ISO_IEC_27001:A.5.12 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.13 | Labelling of information | organisational | attestation: ISO_IEC_27001:A.5.13 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.14 | Information transfer | organisational | attestation: ISO_IEC_27001:A.5.14 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.15 | Access control | hybrid | attestation: ISO_IEC_27001:A.5.15; artifact: policy_access_control (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.16 | Identity management | organisational | attestation: ISO_IEC_27001:A.5.16 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.17 | Authentication information | organisational | attestation: ISO_IEC_27001:A.5.17 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.18 | Access rights | organisational | attestation: ISO_IEC_27001:A.5.18 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.19 | Information security in supplier relationships | hybrid | attestation: ISO_IEC_27001:A.5.19; artifact: policy_supplier (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.20 | Addressing information security within supplier agreements | hybrid | attestation: ISO_IEC_27001:A.5.20; artifact: contract_checklist (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.21 | Managing information security in the ICT supply chain | hybrid | attestation: ISO_IEC_27001:A.5.21; artifact: ai_supply_chain_pins (corroborating); artifact: vendor_register (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.22 | Monitoring, review and change management of supplier services | hybrid | attestation: ISO_IEC_27001:A.5.22; artifact: vendor_register (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.23 | Information security for use of cloud services | hybrid | attestation: ISO_IEC_27001:A.5.23; artifact: exit_plan (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.24 | Information security incident management planning and preparation | hybrid | attestation: ISO_IEC_27001:A.5.24; artifact: incident_response_plan (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.25 | Assessment and decision on information security events | organisational | attestation: ISO_IEC_27001:A.5.25 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.26 | Response to information security incidents | hybrid | attestation: ISO_IEC_27001:A.5.26; artifact: incident_response_plan (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.27 | Learning from information security incidents | hybrid | attestation: ISO_IEC_27001:A.5.27; artifact: corrective_action_log (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.28 | Collection of evidence | organisational | attestation: ISO_IEC_27001:A.5.28 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.29 | Information security during disruption | hybrid | attestation: ISO_IEC_27001:A.5.29; artifact: continuity_plan (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.30 | ICT readiness for business continuity | hybrid | attestation: ISO_IEC_27001:A.5.30; artifact: continuity_plan (corroborating); artifact: restore_test_report (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.31 | Legal, statutory, regulatory and contractual requirements | organisational | attestation: ISO_IEC_27001:A.5.31 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.32 | Intellectual property rights | organisational | attestation: ISO_IEC_27001:A.5.32 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.33 | Protection of records | organisational | attestation: ISO_IEC_27001:A.5.33 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.34 | Privacy and protection of PII | hybrid | attestation: ISO_IEC_27001:A.5.34; artifact: record_of_processing (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.35 | Independent review of information security | hybrid | attestation: ISO_IEC_27001:A.5.35; artifact: internal_audit_report (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.36 | Compliance with policies, rules and standards for information security | organisational | attestation: ISO_IEC_27001:A.5.36 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.5.37 | Documented operating procedures | hybrid | attestation: ISO_IEC_27001:A.5.37; artifact: iso_iec_27001.operating_procedures (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.6.1 | Screening | organisational | attestation: ISO_IEC_27001:A.6.1 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.6.2 | Terms and conditions of employment | organisational | attestation: ISO_IEC_27001:A.6.2 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.6.3 | Information security awareness, education and training | hybrid | attestation: ISO_IEC_27001:A.6.3; artifact: competence_training_record (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.6.4 | Disciplinary process | organisational | attestation: ISO_IEC_27001:A.6.4 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.6.5 | Responsibilities after termination or change of employment | organisational | attestation: ISO_IEC_27001:A.6.5 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.6.6 | Confidentiality or non-disclosure agreements | organisational | attestation: ISO_IEC_27001:A.6.6 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.6.7 | Remote working | organisational | attestation: ISO_IEC_27001:A.6.7 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.6.8 | Information security event reporting | hybrid | attestation: ISO_IEC_27001:A.6.8; artifact: incident_response_plan (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.1 | Physical security perimeters | organisational | attestation: ISO_IEC_27001:A.7.1 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.2 | Physical entry | organisational | attestation: ISO_IEC_27001:A.7.2 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.3 | Securing offices, rooms and facilities | organisational | attestation: ISO_IEC_27001:A.7.3 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.4 | Physical security monitoring | organisational | attestation: ISO_IEC_27001:A.7.4 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.5 | Protecting against physical and environmental threats | organisational | attestation: ISO_IEC_27001:A.7.5 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.6 | Working in secure areas | organisational | attestation: ISO_IEC_27001:A.7.6 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.7 | Clear desk and clear screen | organisational | attestation: ISO_IEC_27001:A.7.7 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.8 | Equipment siting and protection | organisational | attestation: ISO_IEC_27001:A.7.8 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.9 | Security of assets off-premises | organisational | attestation: ISO_IEC_27001:A.7.9 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.10 | Storage media | organisational | attestation: ISO_IEC_27001:A.7.10 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.11 | Supporting utilities | organisational | attestation: ISO_IEC_27001:A.7.11 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.12 | Cabling security | organisational | attestation: ISO_IEC_27001:A.7.12 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.13 | Equipment maintenance | organisational | attestation: ISO_IEC_27001:A.7.13 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.7.14 | Secure disposal or re-use of equipment | organisational | attestation: ISO_IEC_27001:A.7.14 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.1 | User endpoint devices | organisational | attestation: ISO_IEC_27001:A.8.1 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.2 | Privileged access rights | organisational | attestation: ISO_IEC_27001:A.8.2 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.3 | Information access restriction | organisational | attestation: ISO_IEC_27001:A.8.3 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.4 | Access to source code | hybrid | attestation: ISO_IEC_27001:A.8.4; artifact: code_review_rules (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.5 | Secure authentication | organisational | attestation: ISO_IEC_27001:A.8.5 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.6 | Capacity management | organisational | attestation: ISO_IEC_27001:A.8.6 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.7 | Protection against malware | organisational | attestation: ISO_IEC_27001:A.8.7 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.8 | Management of technical vulnerabilities | hybrid | attestation: ISO_IEC_27001:A.8.8; artifact: vulnerability_handling_policy (corroborating); artifact: dependency_update_config (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.9 | Configuration management | hybrid | attestation: ISO_IEC_27001:A.8.9; artifact: iac_definitions (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.10 | Information deletion | organisational | attestation: ISO_IEC_27001:A.8.10 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.11 | Data masking | organisational | attestation: ISO_IEC_27001:A.8.11 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.12 | Data leakage prevention | hybrid | attestation: ISO_IEC_27001:A.8.12; artifact: secret_scanning_config (corroborating) | 90 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.13 | Information backup | hybrid | attestation: ISO_IEC_27001:A.8.13; artifact: policy_backup (corroborating); artifact: restore_test_report (corroborating) | 180 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.14 | Redundancy of information processing facilities | organisational | attestation: ISO_IEC_27001:A.8.14 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.15 | Logging | hybrid | attestation: ISO_IEC_27001:A.8.15; artifact: event_log_evidence (corroborating) | 90 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.16 | Monitoring activities | hybrid | attestation: ISO_IEC_27001:A.8.16; artifact: event_log_evidence (corroborating) | 90 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.17 | Clock synchronization | organisational | attestation: ISO_IEC_27001:A.8.17 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.18 | Use of privileged utility programs | organisational | attestation: ISO_IEC_27001:A.8.18 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.19 | Installation of software on operational systems | organisational | attestation: ISO_IEC_27001:A.8.19 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.20 | Networks security | organisational | attestation: ISO_IEC_27001:A.8.20 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.21 | Security of network services | organisational | attestation: ISO_IEC_27001:A.8.21 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.22 | Segregation of networks | organisational | attestation: ISO_IEC_27001:A.8.22 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.23 | Web filtering | organisational | attestation: ISO_IEC_27001:A.8.23 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.24 | Use of cryptography | hybrid | attestation: ISO_IEC_27001:A.8.24; artifact: policy_cryptography (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.25 | Secure development life cycle | hybrid | attestation: ISO_IEC_27001:A.8.25; artifact: ci_test_workflow (corroborating); artifact: code_review_rules (corroborating) | 180 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.26 | Application security requirements | organisational | attestation: ISO_IEC_27001:A.8.26 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.27 | Secure system architecture and engineering principles | organisational | attestation: ISO_IEC_27001:A.8.27 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.28 | Secure coding | hybrid | attestation: ISO_IEC_27001:A.8.28; artifact: sast_config (corroborating); artifact: secret_scanning_config (corroborating) | 90 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.29 | Security testing in development and acceptance | hybrid | attestation: ISO_IEC_27001:A.8.29; artifact: ci_test_workflow (corroborating); artifact: sast_config (corroborating) | 180 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.30 | Outsourced development | organisational | attestation: ISO_IEC_27001:A.8.30 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.31 | Separation of development, test and production environments | hybrid | attestation: ISO_IEC_27001:A.8.31; artifact: iac_definitions (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.32 | Change management | hybrid | attestation: ISO_IEC_27001:A.8.32; artifact: policy_change_management (corroborating); artifact: code_review_rules (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.33 | Test information | organisational | attestation: ISO_IEC_27001:A.8.33 | 365 | mapping not yet reviewed |
| ISO_IEC_27001:A.8.34 | Protection of information systems during audit testing | organisational | attestation: ISO_IEC_27001:A.8.34 | 365 | mapping not yet reviewed |
<!-- rows:end -->

## Scaffolds

`opencomplai scaffold` writes three starting documents: a statement of applicability, an information
security policy set and a risk treatment plan. A scaffold is a prompt to fill in. An unfilled scaffold
does not count as evidence.

## Timeline

None. This is a standard without legal application dates.

## Gate in CI

```sh
opencomplai check --target ISO_IEC_27001 --gate ISO_IEC_27001 --gate-fail-on missing --repo-root .
```

The command exits 1 when any in-scope row is Missing, and lists the requirement ids.

## What stays attested and why

The organisational rows, and the human half of the hybrid rows, stay attested: they concern decisions,
reviews and records that a repository scan cannot see. Access, identity and device rows wait for
integrations that are not part of this release, so they stay attested until then.

## Review status

The pack status is `evaluated`, set by the parity check. Every mapping is still flagged
`mapping not yet reviewed`; no flag has been cleared.

## Disclaimer

This page and the pack describe what evidence the tool found. They are not a certification, a legal
assessment or a statement that your organisation meets the standard.
