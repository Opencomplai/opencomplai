# ISO/IEC 23894

Today 15 of 23 requirements checked from evidence (target 12); the other 8 take a provider
attestation. The mapping is not yet reviewed.

## What it is

`ISO_IEC_23894` is a native, attestation-led pack for ISO/IEC 23894:2023, guidance on AI risk
management. It carries one row per clause that asks for something: principles, framework
(leadership, integration, implementation, evaluation, improvement) and the risk process
(scope, context, criteria, identification, analysis, evaluation, treatment, monitoring,
recording). Ids and titles follow the standard; each note is a line in this project's own
words. The standard's text is not reproduced.

## Does it apply to you

The pack asks two questions: does the organisation develop, provide or use AI systems, and does
a contract or internal policy commit it to the framework. A commitment gives `applies`, an
organisation with no AI systems gets `not_applicable`, anything else is `voluntary`. Confirm
with your adviser.

## How rows are decided

Every row reads `Unverified` until you record an attestation. Fifteen rows are `hybrid`: a
file or a section of the risk management scaffold gives supporting evidence next to the
attestation. Evidence found gives Met, Partial or Missing. It never lowers a row and never
makes an unattested row Met.

## Requirements

<!-- rows:start -->
| Requirement | Title | Evidence class | Sources | TTL days | Review |
| --- | --- | --- | --- | --- | --- |
| ISO_IEC_23894:Clause 4 | Principles of AI risk management | organisational | attestation: ISO_IEC_23894:Clause 4 | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 5.2 | Leadership and commitment | organisational | attestation: ISO_IEC_23894:Clause 5.2 | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 5.3 | Integration | organisational | attestation: ISO_IEC_23894:Clause 5.3 | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 5.4.1 | Understanding the organization and its context | hybrid | attestation: ISO_IEC_23894:Clause 5.4.1; artifact: scope_statement (corroborating) | 730 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 5.4.2 | Articulating risk management commitment | hybrid | attestation: ISO_IEC_23894:Clause 5.4.2; artifact: policy_ai (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 5.4.3 | Assigning organizational roles, authorities, responsibilities & accountabilities | organisational | attestation: ISO_IEC_23894:Clause 5.4.3 | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 5.4.4 | Allocating resources | organisational | attestation: ISO_IEC_23894:Clause 5.4.4 | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 5.4.5 | Establishing communication and consultation | organisational | attestation: ISO_IEC_23894:Clause 5.4.5 | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 5.5 | Implementation | organisational | attestation: ISO_IEC_23894:Clause 5.5 | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 5.6 | Evaluation | hybrid | attestation: ISO_IEC_23894:Clause 5.6; artifact: management_review_minutes (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 5.7.1 | Adapting | organisational | attestation: ISO_IEC_23894:Clause 5.7.1 | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 5.7.2 | Continually improving | hybrid | attestation: ISO_IEC_23894:Clause 5.7.2; artifact: corrective_action_log (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 6.2 | Communication and consultation | hybrid | attestation: ISO_IEC_23894:Clause 6.2; artifact: iso_iec_23894.risk_process#6.2 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 6.3.2 | Defining the scope | hybrid | attestation: ISO_IEC_23894:Clause 6.3.2; artifact: iso_iec_23894.risk_process#6.3.2 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 6.3.3 | External and internal context | hybrid | attestation: ISO_IEC_23894:Clause 6.3.3; artifact: iso_iec_23894.risk_process#6.3.3 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 6.3.4 | Defining risk criteria | hybrid | attestation: ISO_IEC_23894:Clause 6.3.4; artifact: iso_iec_23894.risk_process#6.3.4 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 6.4.2 | Risk identification | hybrid | attestation: ISO_IEC_23894:Clause 6.4.2; artifact: iso_iec_23894.risk_process#6.4.2 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 6.4.3 | Risk analysis | hybrid | attestation: ISO_IEC_23894:Clause 6.4.3; artifact: iso_iec_23894.risk_process#6.4.3 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 6.4.4 | Risk evaluation | hybrid | attestation: ISO_IEC_23894:Clause 6.4.4; artifact: iso_iec_23894.risk_process#6.4.4 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 6.5.2 | Selection of risk treatment options | hybrid | attestation: ISO_IEC_23894:Clause 6.5.2; artifact: iso_iec_23894.risk_process#6.5.2 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 6.5.3 | Preparing and implementing risk treatment plans | hybrid | attestation: ISO_IEC_23894:Clause 6.5.3; artifact: iso_iec_23894.risk_process#6.5.3 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 6.6 | Monitoring and review | hybrid | attestation: ISO_IEC_23894:Clause 6.6; artifact: iso_iec_23894.risk_process#6.6 (corroborating) | 365 | mapping not yet reviewed |
| ISO_IEC_23894:Clause 6.7 | Recording and reporting | hybrid | attestation: ISO_IEC_23894:Clause 6.7; artifact: iso_iec_23894.risk_process#6.7 (corroborating) | 365 | mapping not yet reviewed |
<!-- rows:end -->

## Scaffolds

`opencomplai scaffold` can create `AI_RISK_MANAGEMENT.md`, a risk management procedure and
register with one section per risk process clause. Fill in the `_fill in_` cells; the
`iso_iec_23894.risk_process` probe then finds each section.

## Timeline

None: a standard without legal application dates.

## Gate in CI

```sh
opencomplai check --target ISO_IEC_23894 --gate ISO_IEC_23894 --gate-fail-on missing --repo-root .
```

The gate exits 1 when a requirement it lists is Missing.

## What stays attested and why

8 rows are `organisational`: they describe leadership, roles, resources and decisions that
leave no file in a repository. Only a person can vouch for them, so each row states why it
takes an attestation. The share checked from evidence is 15 of 23, above the target of 12.

## Review status

Every row carries `mapping not yet reviewed`, at low confidence, and is flagged for founder
review. No flag is cleared.

## Disclaimer

Not an audit, certification or legal assessment. A result says what evidence was found, not
that an organisation meets the guidance.
