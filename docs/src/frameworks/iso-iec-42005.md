# ISO/IEC 42005

## What it is

ISO/IEC 42005:2025 gives guidance on assessing the impact of an AI system on people and
society. Opencomplai carries it as the native target `ISO_IEC_42005`, with 20 requirements.
Each row has a clause id, a title and a note in this project's own words describing the
evidence we look for. The standard's text is not reproduced.

## Does it apply to you

It is voluntary guidance. Nothing in it is a legal duty, and a team that runs an
AI impact assessment can use it as a structure for that work. Two scope answers under
`framework_inputs.ISO_IEC_42005.scope` take clauses out of the report when they do not
fit your system.

## How rows are decided

Each row carries an evidence class:

- **hybrid**: a file or code convention in the repository points at evidence, and an
  attestation from you decides the row.
- **organisational**: only an attestation decides the row.

A row with no evidence reads Missing or Unverified. A supporting probe only points at
evidence and never lifts a row by itself.

## Requirements

17 of 20 requirements are checked from evidence (target 15). The other 3 take an
attestation only.

<!-- rows:start -->
| Requirement | Title | Evidence class | Sources | TTL days | Review |
| --- | --- | --- | --- | --- | --- |
| ISO_IEC_42005:Clause 5.2 | Documenting the process | hybrid | attestation: ISO_IEC_42005:Clause 5.2; artifact: iso_iec_42005.impact_assessment#5.2 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 5.3 | Integration with other organizational management processes | organisational | attestation: ISO_IEC_42005:Clause 5.3 | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 5.4 | Timing of AI system impact assessment | hybrid | attestation: ISO_IEC_42005:Clause 5.4; artifact: iso_iec_42005.impact_assessment#5.4 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 5.5 | Scope of the AI system impact assessment | hybrid | attestation: ISO_IEC_42005:Clause 5.5; artifact: iso_iec_42005.impact_assessment#5.5 (corroborating) | 730 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 5.6 | Allocating responsibilities | hybrid | attestation: ISO_IEC_42005:Clause 5.6; artifact: iso_iec_42005.impact_assessment#5.6 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 5.7 | Establishing thresholds for sensitive uses, restricted uses and impact scales | hybrid | attestation: ISO_IEC_42005:Clause 5.7; artifact: iso_iec_42005.impact_assessment#5.7 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 5.8 | Performing the AI system impact assessment | organisational | attestation: ISO_IEC_42005:Clause 5.8 | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 5.9 | Analysing the results of the AI system impact assessment | organisational | attestation: ISO_IEC_42005:Clause 5.9 | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 5.10 | Recording and reporting | hybrid | attestation: ISO_IEC_42005:Clause 5.10; artifact: iso_iec_42005.impact_assessment#5.10 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 5.11 | Approval process | hybrid | attestation: ISO_IEC_42005:Clause 5.11; artifact: iso_iec_42005.impact_assessment#5.11 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 5.12 | Monitoring and review | hybrid | attestation: ISO_IEC_42005:Clause 5.12; artifact: iso_iec_42005.impact_assessment#5.12 (corroborating) | 90 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 6.2 | Scope of the AI system impact assessment | hybrid | attestation: ISO_IEC_42005:Clause 6.2; artifact: iso_iec_42005.impact_assessment#6.2 (corroborating) | 730 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 6.3 | AI system information | hybrid | attestation: ISO_IEC_42005:Clause 6.3; artifact: iso_iec_42005.impact_assessment#6.3 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 6.4 | Data information and quality | hybrid | attestation: ISO_IEC_42005:Clause 6.4; artifact: iso_iec_42005.impact_assessment#6.4 (corroborating) | 180 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 6.5 | Algorithm and model information | hybrid | attestation: ISO_IEC_42005:Clause 6.5; artifact: iso_iec_42005.impact_assessment#6.5 (corroborating) | 180 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 6.6 | Deployment environment | hybrid | attestation: ISO_IEC_42005:Clause 6.6; artifact: iso_iec_42005.impact_assessment#6.6 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 6.7 | Relevant interested parties | hybrid | attestation: ISO_IEC_42005:Clause 6.7; artifact: iso_iec_42005.impact_assessment#6.7 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 6.8.2 | Benefits and harms | hybrid | attestation: ISO_IEC_42005:Clause 6.8.2; artifact: iso_iec_42005.impact_assessment#6.8.2 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 6.8.3 | AI system failures and reasonably foreseeable misuse | hybrid | attestation: ISO_IEC_42005:Clause 6.8.3; artifact: iso_iec_42005.impact_assessment#6.8.3 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_42005:Clause 6.9 | Measures to address harms and benefits | hybrid | attestation: ISO_IEC_42005:Clause 6.9; artifact: iso_iec_42005.impact_assessment#6.9 (corroborating) | 365 | mapping not yet reviewed |
<!-- rows:end -->

## Scaffolds

`opencomplai scaffold` writes a starting `AI_IMPACT_ASSESSMENT.md` with one marked
section per clause. Each section holds a `_fill in_` marker until you write it.

## Timeline (none)

This pack has no timeline: a standard without legal application dates.

## Gate in CI

```sh
opencomplai check --target ISO_IEC_42005 --gate ISO_IEC_42005 --gate-fail-on missing --repo-root .
```

The gate exits 1 when a row reads Missing.

## What stays attested and why

Clauses 5.3, 5.8 and 5.9 concern how the organisation runs and governs its assessment
process. No file in a repository shows that, so these rows take an attestation only.

## Review status

The row mappings are this project's own, flagged low confidence: mapping not yet reviewed.

## Disclaimer

This page describes what the tool checks. It is not an audit, certification or legal
assessment. Percentages and counts are draft estimates.
