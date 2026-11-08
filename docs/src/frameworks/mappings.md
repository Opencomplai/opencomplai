# Framework mappings

How each requirement of NIST AI RMF 1.0, ISO/IEC 42001:2023 and ISO/IEC 27090:2026
relates to the EU AI Act and to the other two frameworks, followed by the further native
packs and their links to the EU AI Act, ISO/IEC 27001 and ISO/IEC 42001. This page is
generated from the data files in `packages/core/src/opencomplai_core/data/`; do not edit
it by hand.

- **NIST AI RMF:** the EU AI Act column decides the verdict, except for an article that
  an attestation decides (today Art. 4), which counts as no NIST evidence and is set
  aside. The evidence of the other articles is re-projected onto the subcategory (worst
  status, lowest confidence). A subcategory with no article, or only a set-aside one
  (GOVERN 2.2), takes a provider attestation instead; MAP 3.4 (Art. 4 and Art. 26) holds
  at Unverified at best.
- **NIST AI RMF to ISO/IEC 42001** links come from NIST's own crosswalk ("NIST AI RMF to
  ISO/IEC FDIS 42001 AI Management System Crosswalk"). Its Annex B guidance numbers are
  read as the Annex A controls, and sub-clauses 7.5.x, 9.2.x and 9.3.x as their parent rows.
- **ISO/IEC 27090 to ISO/IEC 27001 Annex A and SOC 2** anchors are given per row,
  as control ids only; rows without an anchor show "—".
- **Every other link** is this project's own mapping, at low confidence.
- **ISO/IEC 42001 and ISO/IEC 27090** rows show clause ids and short headings only, never
  standard text.
- Every mapping is flagged for founder review. A link says two requirements cover related
  ground. It is not a claim that meeting one meets the other.

## NIST AI RMF 1.0

| Subcategory | EU AI Act (confidence) | Why | ISO/IEC 42001 | ISO/IEC 27090 |
|---|---|---|---|---|
| GOVERN 1.1 | Art. 5 (low), Art. 6 (low), Art. 16 (low) | Knowing which legal duties apply: prohibited-practice screening, risk classification and the provider duties. | Clause 4.1, Clause 6.2, A.2.2, A.2.4 | — |
| GOVERN 1.2 | Art. 17 (low) | The quality management system is where trustworthiness goals become policy. | Clause 4.4, Clause 5.2, A.2.2, A.6.1.2, A.6.1.3, A.9.3, A.10.3 | 5.2 |
| GOVERN 1.3 | Art. 9 (low) | The risk management system sets how much risk work a system needs. | Clause 6.1.1, Clause 6.1.2, Clause 6.1.3 | — |
| GOVERN 1.4 | Art. 9 (medium), Art. 17 (low) | Risk management system and its documented procedures. | Clause 6.1.2, Clause 6.1.3, Clause 8.3 | — |
| GOVERN 1.5 | Art. 9 (low), Art. 72 (low) | Art. 9 requires regular review of the risk process; post-market monitoring feeds it. | Clause 8.2, Clause 8.3, Clause 8.4 | — |
| GOVERN 1.6 | Art. 49 (low) | Registration in the EU database is the closest EU evidence of an inventory; it covers high-risk systems only. | A.4.2, A.4.3, A.4.4, A.4.5, A.4.6 | 5.2 |
| GOVERN 1.7 | none: attestation | The EU AI Act evidence the tool gathers has no decommissioning record. | A.6.2.6 | 7.3 |
| GOVERN 2.1 | Art. 17 (low) | The quality management system includes an accountability framework. | Clause 5.3, Clause 7.1, Clause 7.2, Clause 7.3, Clause 7.4, Clause 9.1, A.3.2 | 5.2 |
| GOVERN 2.2 | Art. 4 (medium) | AI literacy measures for staff and others operating the system. | Clause 7.2 | — |
| GOVERN 2.3 | Art. 17 (low) | Management responsibility is part of the accountability framework of the QMS. | Clause 5.1, Clause 5.2, Clause 9.3 | — |
| GOVERN 3.1 | none: attestation | No EU AI Act evidence covers team diversity. | A.4.6, A.5.4 | — |
| GOVERN 3.2 | Art. 14 (medium), Art. 26 (low) | Human oversight design (provider) and assigning oversight to competent people (deployer). | Clause 7.2, Clause 9.3, A.4.6, A.5.3, A.6.1.3, A.9.3 | 6.11 |
| GOVERN 4.1 | none: attestation | Organisational culture is outside the EU AI Act evidence. | A.5.2, A.5.4, A.6.1.2, A.6.1.3, A.9.2, A.9.3, A.10.3 | 5.4 |
| GOVERN 4.2 | Art. 9 (low), Art. 13 (low), Art. 27 (low) | Documented risks, information to deployers and the fundamental rights impact assessment. | Clause 6.1.4, Clause 7.4, A.5.4, A.5.5, A.8.5 | — |
| GOVERN 4.3 | Art. 9 (low), Art. 73 (low) | Testing within risk management and serious-incident handling. | A.6.1.2, A.6.1.3, A.6.2.4, A.6.2.6, A.6.2.7, A.8.2, A.8.3, A.8.4, A.8.5 | — |
| GOVERN 5.1 | Art. 72 (low) | Post-market monitoring collects experience from deployers; wider external feedback is not covered. | A.5.3, A.5.4, A.8.3, A.10.4 | — |
| GOVERN 5.2 | Art. 72 (low) | Post-market monitoring results feed back into the system. | A.5.4, A.5.5, A.6.1.3, A.6.2.6, A.8.3, A.10.4 | — |
| GOVERN 6.1 | Art. 24 (low), Art. 25 (low), Art. 53 (low) | Value-chain duties, distributor checks and the GPAI copyright policy. | A.10.2, A.10.3 | 5.5, B.3 |
| GOVERN 6.2 | Art. 25 (low) | Written agreements with suppliers along the value chain. | A.10.2, A.10.3 | 5.5 |
| MAP 1.1 | Art. 6 (low), Art. 11 (low), Art. 13 (low) | Intended purpose drives classification and is stated in the documentation and instructions. | Clause 6.1.4, A.5.2, A.5.3, A.5.4, A.5.5 | — |
| MAP 1.2 | none: attestation | Team composition is outside the EU AI Act evidence. | Clause 7.2, A.4.6 | — |
| MAP 1.3 | none: attestation | Mission and goals are outside the EU AI Act evidence. | Clause 4.1, Clause 5.2, Clause 6.2, Clause 7.3, Clause 7.4, Clause 7.5 | — |
| MAP 1.4 | none: attestation | Business value is outside the EU AI Act evidence. | Clause 4.1, Clause 5.1, A.5.2, A.6.2.2, A.9.4, A.10.4 | — |
| MAP 1.5 | Art. 9 (low) | Art. 9 requires residual risk to be judged acceptable. | Clause 6.1.1 | — |
| MAP 1.6 | Art. 17 (low) | Design control procedures in the QMS. | A.5.4, A.5.5, A.6.2.2 | — |
| MAP 2.1 | Art. 11 (low) | The technical documentation describes the system's tasks and methods. | A.4.2, A.4.3, A.4.4, A.4.5, A.4.6, A.6.2.3 | — |
| MAP 2.2 | Art. 13 (medium), Art. 14 (low) | Instructions state limitations and how output is used and overseen. | A.6.2.7, A.8.2, A.9.3 | — |
| MAP 2.3 | Art. 10 (medium) | Data governance covers collection, selection and representativeness. | A.6.1.3, A.6.2.4, A.6.2.7, A.7.2, A.7.3, A.7.4, A.7.5, A.7.6 | 6.2 |
| MAP 3.1 | none: attestation | Benefits are outside the EU AI Act evidence. | A.5.2, A.5.3, A.5.4, A.5.5 | — |
| MAP 3.2 | Art. 9 (low) | Risk estimation covers the costs of errors. | Clause 8.2, Clause 8.3, Clause 8.4, A.5.2, A.5.3, A.5.4, A.5.5 | — |
| MAP 3.3 | Art. 6 (low), Art. 13 (low) | Scope follows from classification and the stated intended purpose. | Clause 4.3, A.5.2, A.5.3, A.5.4, A.5.5 | — |
| MAP 3.4 | Art. 4 (low), Art. 26 (low) | AI literacy and deployers' competent operators. | Clause 7.2, A.4.6 | — |
| MAP 3.5 | Art. 14 (medium) | Human oversight measures. | A.6.1.3, A.6.2.7, A.8.2 | — |
| MAP 4.1 | Art. 25 (low), Art. 53 (low) | Third-party components along the value chain; GPAI copyright policy. | Clause 4.1, A.2.2, A.9.2, A.9.4 | 5.5, B.3 |
| MAP 4.2 | Art. 9 (low), Art. 25 (low) | Risk controls including those for supplied components. | A.6.2.7, A.8.2, A.10.3 | 5.5 |
| MAP 5.1 | Art. 9 (medium), Art. 27 (low) | Risk estimation and the fundamental rights impact assessment. | Clause 6.1.2, A.5.2 | 5.6 |
| MAP 5.2 | Art. 72 (low) | Post-market monitoring gathers experience from users of the system. | A.6.1.3, A.6.2.6, A.8.3 | — |
| MEASURE 1.1 | Art. 9 (low), Art. 15 (low) | Risk management selects measures; Art. 15 requires declared accuracy metrics. | Clause 6.1.1, Clause 6.1.2 | 5.6 |
| MEASURE 1.2 | Art. 9 (low), Art. 72 (low) | Review of measures and post-market evaluation. | A.5.2, A.5.4, A.5.5, A.6.2.4 | 7.2 |
| MEASURE 1.3 | Art. 43 (low) | Conformity assessment is the EU route to independent assessment. | Clause 6.1.2, Clause 9.2, A.5.2, A.5.4, A.5.5 | 5.7 |
| MEASURE 2.1 | Art. 9 (low), Art. 11 (low) | Testing under risk management, documented in the technical documentation. | A.4.2, A.6.2.4, A.6.2.7, A.8.4 | — |
| MEASURE 2.2 | none: attestation | Human-subject evaluation is outside the EU AI Act evidence the tool gathers. | A.6.2.4 | — |
| MEASURE 2.3 | Art. 15 (medium) | Accuracy levels and metrics. | A.6.2.6, A.7.4 | — |
| MEASURE 2.4 | Art. 12 (low), Art. 26 (low), Art. 72 (medium) | Logs, deployer monitoring and post-market monitoring. | Clause 9.1, A.6.2.6, A.6.2.8 | 7.4, 7.5 |
| MEASURE 2.5 | Art. 13 (low), Art. 15 (low) | Robustness and the documented limits of the system. | A.6.2.4, A.6.2.5, A.6.2.7, A.8.2 | 6.3 |
| MEASURE 2.6 | Art. 9 (low), Art. 15 (low) | Risk management and resilience to errors and faults (fail-safe plans). | Clause 8.2, A.6.2.4, A.6.2.6, A.6.2.8 | 5.7, 6.3 |
| MEASURE 2.7 | Art. 15 (medium), Art. 55 (low) | Cybersecurity of high-risk systems; adversarial testing and cybersecurity for GPAI with systemic risk. | A.2.3, A.3.2, A.5.2, A.6.1.2, A.6.2.3, A.7.2, A.9.3 | 5.1, 5.3, 5.4, 5.6, 5.7, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11, 7.6, 7.7, 7.8, 7.9, B.2, B.4, B.5 |
| MEASURE 2.8 | Art. 13 (low), Art. 50 (low) | Transparency to deployers and to people interacting with the system. | Clause 6.1.2, A.5.4, A.5.5, A.6.1.2, A.7.2, A.9.3 | — |
| MEASURE 2.9 | Art. 13 (low), Art. 14 (low) | Instructions and oversight measures help interpret output. | A.6.2.5, A.6.2.7, A.7.5, A.8.2 | — |
| MEASURE 2.10 | Art. 10 (low) | Safeguards for special categories of personal data in data governance. | A.2.3, A.5.2, A.7.2, A.7.3 | 6.4, 6.6, 6.8, B.6, B.7 |
| MEASURE 2.11 | Art. 10 (medium) | Data governance requires examination of possible biases. | A.5.4, A.5.5 | — |
| MEASURE 2.12 | Art. 53 (low) | GPAI documentation includes energy consumption; nothing for other systems. | A.4.5, A.5.5 | — |
| MEASURE 2.13 | none: attestation | Evaluating the test process itself is outside the EU AI Act evidence. | A.6.2.4, A.6.2.6 | — |
| MEASURE 3.1 | Art. 9 (low), Art. 12 (low), Art. 72 (low) | Ongoing risk identification, logs and post-market monitoring. | Clause 4.4, Clause 8.2, Clause 8.4 | 7.4 |
| MEASURE 3.2 | none: attestation | No EU AI Act evidence for risks that cannot yet be measured. | Clause 10.1, A.6.2.6, A.6.2.8 | — |
| MEASURE 3.3 | none: attestation | End-user appeal channels are outside the EU AI Act evidence the tool gathers. | A.8.2, A.8.3, A.8.4 | — |
| MEASURE 4.1 | none: attestation | Consulting domain experts is outside the EU AI Act evidence. | Clause 9.1, A.5.4, A.5.5, A.6.2.4 | — |
| MEASURE 4.2 | none: attestation | Expert validation of results is outside the EU AI Act evidence. | Clause 9.1, Clause 9.2, A.8.2, A.8.3 | — |
| MEASURE 4.3 | Art. 72 (low) | Post-market monitoring uses field data on performance. | Clause 9.3, A.6.2.6, A.6.2.7 | — |
| MANAGE 1.1 | Art. 9 (low), Art. 43 (low) | Risk acceptance and conformity assessment before placing on the market. | A.6.1.3, A.6.2.4, A.9.2, A.9.3, A.9.4 | — |
| MANAGE 1.2 | Art. 9 (low) | Risk management prioritises measures. | Clause 6.1.2, Clause 6.1.3, Clause 6.1.4, Clause 9.3 | — |
| MANAGE 1.3 | Art. 9 (medium) | Risk management measures for identified risks. | Clause 6.1.1, Clause 6.1.2, Clause 6.1.3, Clause 6.1.4 | 5.1, 7.2 |
| MANAGE 1.4 | Art. 9 (low), Art. 13 (low) | Residual risks are judged and communicated to deployers. | A.5.3, A.5.4, A.6.2.7, A.8.2 | — |
| MANAGE 2.1 | none: attestation | Resourcing and non-AI alternatives are outside the EU AI Act evidence. | Clause 7.1, A.4.2 | — |
| MANAGE 2.2 | Art. 72 (low) | Post-market monitoring keeps the system performing as intended. | Clause 7.1, Clause 10.1, A.3.3, A.6.1.2, A.6.1.3, A.6.2.4, A.6.2.6, A.7.2 | — |
| MANAGE 2.3 | Art. 72 (low), Art. 73 (low) | Post-market monitoring and serious-incident handling. | Clause 6.1.1, Clause 6.1.2, Clause 6.1.3, Clause 10.2 | — |
| MANAGE 2.4 | Art. 14 (medium) | Oversight includes the ability to stop or override the system. | A.6.1.3, A.6.2.7, A.8.2, A.9.4 | — |
| MANAGE 3.1 | Art. 25 (low) | Duties shared with third parties along the value chain. | A.10.2, A.10.3 | 5.5 |
| MANAGE 3.2 | Art. 53 (low) | GPAI providers must inform downstream providers of the model's capabilities and limits. | A.4.4, A.6.2.6 | 5.5, 6.7, B.3, B.4 |
| MANAGE 4.1 | Art. 72 (medium), Art. 73 (low) | Post-market monitoring plan and incident reporting. | Clause 9.2, A.6.2.6, A.8.3, A.10.4 | 7.3, 7.5 |
| MANAGE 4.2 | Art. 17 (low), Art. 72 (low) | QMS improvement and post-market monitoring. | Clause 9.3, A.6.2.4, A.6.2.6 | — |
| MANAGE 4.3 | Art. 73 (medium) | Reporting of serious incidents. | Clause 9.3, A.6.2.6, A.8.5 | — |

## ISO/IEC 42001:2023

| Id | Heading | EU AI Act | NIST AI RMF | ISO/IEC 27090 |
|---|---|---|---|---|
| Clause 4.1 | Understanding the organization and its context | — | GOVERN 1.1, MAP 1.3, MAP 1.4, MAP 4.1 | — |
| Clause 4.2 | Understanding the needs and expectations of interested parties | — | — | — |
| Clause 4.3 | Determining the scope of the AI management system | — | MAP 3.3 | — |
| Clause 4.4 | AI management system | Art. 17 | GOVERN 1.2, MEASURE 3.1 | — |
| Clause 5.1 | Leadership and commitment | Art. 17 | GOVERN 2.3, MAP 1.4 | 5.2 |
| Clause 5.2 | AI policy | Art. 17 | GOVERN 1.2, GOVERN 2.3, MAP 1.3 | — |
| Clause 5.3 | Roles, responsibilities and authorities | Art. 17 | GOVERN 2.1 | — |
| Clause 6.1.1 | General | Art. 9 | GOVERN 1.3, MAP 1.5, MEASURE 1.1, MANAGE 1.3, MANAGE 2.3 | — |
| Clause 6.1.2 | AI risk assessment | Art. 9 | GOVERN 1.3, GOVERN 1.4, MAP 5.1, MEASURE 1.1, MEASURE 1.3, MEASURE 2.8, MANAGE 1.2, MANAGE 1.3, MANAGE 2.3 | 5.6 |
| Clause 6.1.3 | AI risk treatment | Art. 9 | GOVERN 1.3, GOVERN 1.4, MANAGE 1.2, MANAGE 1.3, MANAGE 2.3 | 5.1, 7.2 |
| Clause 6.1.4 | AI system impact assessment | Art. 9, Art. 27 | GOVERN 4.2, MAP 1.1, MANAGE 1.2, MANAGE 1.3 | — |
| Clause 6.2 | AI objectives and planning to achieve them | — | GOVERN 1.1, MAP 1.3 | — |
| Clause 6.3 | Planning of changes | Art. 25 | — | — |
| Clause 7.1 | Resources | — | GOVERN 2.1, MANAGE 2.1, MANAGE 2.2 | — |
| Clause 7.2 | Competence | Art. 4 | GOVERN 2.1, GOVERN 2.2, GOVERN 3.2, MAP 1.2, MAP 3.4 | — |
| Clause 7.3 | Awareness | Art. 4 | GOVERN 2.1, MAP 1.3 | — |
| Clause 7.4 | Communication | Art. 13, Art. 50 | GOVERN 2.1, GOVERN 4.2, MAP 1.3 | — |
| Clause 7.5 | Documented information | Art. 11 | MAP 1.3 | — |
| Clause 8.1 | Operational planning and control | Art. 17 | — | 7.3 |
| Clause 8.2 | AI risk assessment | Art. 9 | GOVERN 1.5, MAP 3.2, MEASURE 2.6, MEASURE 3.1 | 5.6 |
| Clause 8.3 | AI risk treatment | Art. 9 | GOVERN 1.4, GOVERN 1.5, MAP 3.2 | — |
| Clause 8.4 | AI system impact assessment | Art. 27 | GOVERN 1.5, MAP 3.2, MEASURE 3.1 | — |
| Clause 9.1 | Monitoring, measurement, analysis and evaluation | Art. 12, Art. 72 | GOVERN 2.1, MEASURE 2.4, MEASURE 4.1, MEASURE 4.2 | 7.4 |
| Clause 9.2 | Internal audit | Art. 43 | MEASURE 1.3, MEASURE 4.2, MANAGE 4.1 | — |
| Clause 9.3 | Management review | Art. 17 | GOVERN 2.3, GOVERN 3.2, MEASURE 4.3, MANAGE 1.2, MANAGE 4.2, MANAGE 4.3 | — |
| Clause 10.1 | Continual improvement | Art. 72 | MEASURE 3.2, MANAGE 2.2 | — |
| Clause 10.2 | Nonconformity and corrective action | Art. 73 | MANAGE 2.3 | — |
| A.2.2 | AI policy | Art. 17 | GOVERN 1.1, GOVERN 1.2, MAP 4.1 | 5.2 |
| A.2.3 | Alignment with other organizational policies | — | MEASURE 2.7, MEASURE 2.10 | — |
| A.2.4 | Review of the AI policy | — | GOVERN 1.1 | — |
| A.3.2 | AI roles and responsibilities | Art. 17, Art. 26 | GOVERN 2.1, MEASURE 2.7 | 5.2 |
| A.3.3 | Reporting of concerns | — | MANAGE 2.2 | — |
| A.4.2 | Resource documentation | Art. 11 | GOVERN 1.6, MAP 2.1, MEASURE 2.1, MANAGE 2.1 | — |
| A.4.3 | Data resources | Art. 10 | GOVERN 1.6, MAP 2.1 | — |
| A.4.4 | Tooling resources | Art. 11 | GOVERN 1.6, MAP 2.1, MANAGE 3.2 | 7.6 |
| A.4.5 | System and computing resources | Art. 11 | GOVERN 1.6, MAP 2.1, MEASURE 2.12 | B.2 |
| A.4.6 | Human resources | Art. 4, Art. 14 | GOVERN 1.6, GOVERN 3.1, GOVERN 3.2, MAP 1.2, MAP 2.1, MAP 3.4 | — |
| A.5.2 | AI system impact assessment process | Art. 9, Art. 27 | GOVERN 4.1, MAP 1.1, MAP 1.4, MAP 3.1, MAP 3.2, MAP 3.3, MAP 5.1, MEASURE 1.2, MEASURE 1.3, MEASURE 2.7, MEASURE 2.10 | — |
| A.5.3 | Documentation of AI system impact assessments | Art. 27 | GOVERN 3.2, GOVERN 5.1, MAP 1.1, MAP 3.1, MAP 3.2, MAP 3.3, MANAGE 1.4 | — |
| A.5.4 | Assessing AI system impact on individuals or groups of individuals | Art. 27 | GOVERN 3.1, GOVERN 4.1, GOVERN 4.2, GOVERN 5.1, GOVERN 5.2, MAP 1.1, MAP 1.6, MAP 3.1, MAP 3.2, MAP 3.3, MEASURE 1.2, MEASURE 1.3, MEASURE 2.8, MEASURE 2.11, MEASURE 4.1, MANAGE 1.4 | — |
| A.5.5 | Assessing societal impacts of AI systems | Art. 27 | GOVERN 4.2, GOVERN 5.2, MAP 1.1, MAP 1.6, MAP 3.1, MAP 3.2, MAP 3.3, MEASURE 1.2, MEASURE 1.3, MEASURE 2.8, MEASURE 2.11, MEASURE 2.12, MEASURE 4.1 | — |
| A.6.1.2 | Objectives for responsible development of AI system | Art. 17 | GOVERN 1.2, GOVERN 4.1, GOVERN 4.3, MEASURE 2.7, MEASURE 2.8, MANAGE 2.2 | — |
| A.6.1.3 | Processes for responsible AI system design and development | Art. 17 | GOVERN 1.2, GOVERN 3.2, GOVERN 4.1, GOVERN 4.3, GOVERN 5.2, MAP 2.3, MAP 3.5, MAP 5.2, MANAGE 1.1, MANAGE 2.2, MANAGE 2.4 | 5.4 |
| A.6.2.2 | AI system requirements and specification | Art. 11 | MAP 1.4, MAP 1.6 | — |
| A.6.2.3 | Documentation of AI system design and development | Art. 11 | MAP 2.1, MEASURE 2.7 | 5.1, 5.5, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10 |
| A.6.2.4 | AI system verification and validation | Art. 9, Art. 15 | GOVERN 4.3, MAP 2.3, MEASURE 1.2, MEASURE 2.1, MEASURE 2.2, MEASURE 2.5, MEASURE 2.6, MEASURE 2.13, MEASURE 4.1, MANAGE 1.1, MANAGE 2.2, MANAGE 4.2 | 5.4, 5.7, 6.3 |
| A.6.2.5 | AI system deployment | Art. 43 | MEASURE 2.5, MEASURE 2.9 | — |
| A.6.2.6 | AI system operation and monitoring | Art. 26, Art. 72 | GOVERN 1.7, GOVERN 4.3, GOVERN 5.2, MAP 5.2, MEASURE 2.3, MEASURE 2.4, MEASURE 2.6, MEASURE 2.13, MEASURE 3.2, MEASURE 4.3, MANAGE 2.2, MANAGE 3.2, MANAGE 4.1, MANAGE 4.2, MANAGE 4.3 | 5.1, 5.5, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 7.3, 7.4, 7.5 |
| A.6.2.7 | AI system technical documentation | Art. 11 | GOVERN 4.3, MAP 2.2, MAP 2.3, MAP 3.5, MAP 4.2, MEASURE 2.1, MEASURE 2.5, MEASURE 2.9, MEASURE 4.3, MANAGE 1.4, MANAGE 2.4 | — |
| A.6.2.8 | AI system recording of event logs | Art. 12 | MEASURE 2.4, MEASURE 2.6, MEASURE 3.2 | 7.5 |
| A.7.2 | Data for development and enhancement of AI system | Art. 10 | MAP 2.3, MEASURE 2.7, MEASURE 2.8, MEASURE 2.10, MANAGE 2.2 | B.6 |
| A.7.3 | Acquisition of data | Art. 10 | MAP 2.3, MEASURE 2.10 | 6.2 |
| A.7.4 | Quality of data for AI systems | Art. 10 | MAP 2.3, MEASURE 2.3 | 6.2 |
| A.7.5 | Data provenance | Art. 10 | MAP 2.3, MEASURE 2.9 | 5.5, 6.2, 6.11 |
| A.7.6 | Data preparation | Art. 10 | MAP 2.3 | — |
| A.8.2 | System documentation and information for users | Art. 13 | GOVERN 4.3, MAP 2.2, MAP 3.5, MAP 4.2, MEASURE 2.5, MEASURE 2.9, MEASURE 3.3, MEASURE 4.2, MANAGE 1.4, MANAGE 2.4 | — |
| A.8.3 | External reporting | Art. 73 | GOVERN 4.3, GOVERN 5.1, GOVERN 5.2, MAP 5.2, MEASURE 3.3, MEASURE 4.2, MANAGE 4.1 | — |
| A.8.4 | Communication of incidents | Art. 73 | GOVERN 4.3, MEASURE 2.1, MEASURE 3.3 | — |
| A.8.5 | Information for interested parties | Art. 13, Art. 50 | GOVERN 4.2, GOVERN 4.3, MANAGE 4.3 | — |
| A.9.2 | Processes for responsible use of AI systems | Art. 26 | GOVERN 4.1, MAP 4.1, MANAGE 1.1 | — |
| A.9.3 | Objectives for responsible use of AI system | Art. 26 | GOVERN 1.2, GOVERN 3.2, GOVERN 4.1, MAP 2.2, MEASURE 2.7, MEASURE 2.8, MANAGE 1.1 | — |
| A.9.4 | Intended use of the AI system | Art. 13, Art. 26 | MAP 1.4, MAP 4.1, MANAGE 1.1, MANAGE 2.4 | — |
| A.10.2 | Allocating responsibilities | Art. 25 | GOVERN 6.1, GOVERN 6.2, MANAGE 3.1 | 5.5 |
| A.10.3 | Suppliers | Art. 25 | GOVERN 1.2, GOVERN 4.1, GOVERN 6.1, GOVERN 6.2, MAP 4.2, MANAGE 3.1 | 5.5, 6.7, B.3, B.7 |
| A.10.4 | Customers | Art. 13, Art. 25 | GOVERN 5.1, GOVERN 5.2, MAP 1.4, MANAGE 4.1 | — |

## ISO/IEC 27090:2026

ISO/IEC 27001 Annex A and SOC 2 columns give control ids only, for teams that already run one of those programmes. Checks lists the output evaluators a row also reads and, marked probe, the file or code probes that add supporting evidence to an attestation.

| Id | Heading | What we look for | Checks | EU AI Act | NIST AI RMF | ISO/IEC 42001 | ISO/IEC 27001 Annex A | SOC 2 |
|---|---|---|---|---|---|---|---|---|
| 5.1 | General | Conventional security controls are chosen from a risk assessment, and the AI-specific threats in clause 6 are considered at every life-cycle stage. | — | Art. 9, Art. 15 | MEASURE 2.7, MANAGE 1.3 | Clause 6.1.3, A.6.2.3, A.6.2.6 | A.8.15, A.8.16, A.8.27 | CC3.2, CC5.1 |
| 5.2 | AI governance programme | AI security is owned by the organisation's AI governance, and every AI system in use is known and accounted for. | — | Art. 17 | GOVERN 1.2, GOVERN 1.6, GOVERN 2.1 | Clause 5.1, A.2.2, A.3.2 | A.5.1, A.5.2 | CC1.3, CC5.3 |
| 5.3 | Zero trust principles | Models, agents and the tools they call get only the access they need, and every request to them is authenticated and authorised. | — | Art. 15 | MEASURE 2.7 | — | A.5.15, A.8.2, A.8.5, A.8.27 | CC6.1, CC6.2, CC6.3 |
| 5.4 | Applying software engineering best practices to AI | Secure development practice (review, testing, change control) covers models, data pipelines and the code around them. | — | Art. 15, Art. 17 | GOVERN 4.1, MEASURE 2.7 | A.6.1.3, A.6.2.4 | A.8.25, A.8.28, A.8.29 | CC8.1 |
| 5.5 | Supply chain management | Third-party models, datasets, libraries and hosted AI services are vetted, pinned and tracked, with security expectations agreed with their providers. | ai_supply_chain_pins (probe) | Art. 25 | GOVERN 6.1, GOVERN 6.2, MAP 4.1, MAP 4.2, MANAGE 3.1, MANAGE 3.2 | A.6.2.3, A.6.2.6, A.7.5, A.10.2, A.10.3 | A.5.19, A.5.20, A.5.21, A.5.22, A.5.23, A.8.8 | CC6.8, CC7.1, CC9.1, CC9.2 |
| 5.6 | Threat modelling | Each AI system has a threat model that includes AI-specific attacks, feeds the risk assessment and is updated when the system changes. | ai_threat_model (probe) | Art. 9, Art. 15 | MAP 5.1, MEASURE 1.1, MEASURE 2.7 | Clause 6.1.2, Clause 8.2 | A.5.7 | CC3.2 |
| 5.7 | Red teaming | The system is attacked on purpose, for example with jailbreak and injection prompts, before release and after significant changes. | EVAL_ADVERSARIAL_V1, ai_red_team_report (probe) | Art. 15, Art. 55 | MEASURE 1.3, MEASURE 2.6, MEASURE 2.7 | A.6.2.4 | A.8.25, A.8.28, A.8.29 | CC6.6, CC6.7, CC7.1, CC8.1, PI1.3 |
| 6.2 | Data poisoning attack | Training, fine-tuning and retrieval data, including data collected in operation, is checked for provenance and tampering before use. | — | Art. 9, Art. 10, Art. 15 | MAP 2.3, MEASURE 2.7 | A.6.2.3, A.6.2.6, A.7.3, A.7.4, A.7.5 | A.5.12, A.8.25, A.8.29 | CC3.2, PI1.2 |
| 6.3 | Evasion attack | Inputs crafted to make the model err are tested for, the system is hardened and monitored against them, and known weaknesses are stated in the instructions for use. | — | Art. 13, Art. 15 | MEASURE 2.5, MEASURE 2.6, MEASURE 2.7 | A.6.2.3, A.6.2.4, A.6.2.6 | A.8.29 | CC7.1 |
| 6.4 | Membership inference | The system does not reveal whether a given record was part of its training data. | — | Art. 10, Art. 15 | MEASURE 2.7, MEASURE 2.10 | A.6.2.3, A.6.2.6 | A.8.11, A.8.12 | C1.1, C1.2, CC6.1 |
| 6.5 | Model exfiltration | Query access cannot be used to rebuild a working copy of the model. | rate_limiting_config (probe) | Art. 15 | MEASURE 2.7 | A.6.2.3, A.6.2.6 | A.8.3, A.8.16 | CC6.1, CC6.2, CC6.3, CC7.2 |
| 6.6 | Model inversion | Outputs cannot be used to reconstruct training data. | — | Art. 10, Art. 15 | MEASURE 2.7, MEASURE 2.10 | A.6.2.3, A.6.2.6 | A.8.3, A.8.11, A.8.12 | C1.1, C1.2, CC6.1, CC6.2, CC6.3, CC7.2 |
| 6.7 | Direct model poisoning | Model weights and pre-trained components are protected against tampering in development and in operation. | — | Art. 15, Art. 25 | MEASURE 2.7, MANAGE 3.2 | A.6.2.3, A.6.2.6, A.10.3 | A.5.21, A.8.30, A.8.32 | CC6.8, CC8.1, CC9.2 |
| 6.8 | Sensitive model output | Outputs do not disclose confidential data such as training records or other users' inputs. | EVAL_DATA_LEAKAGE_V1 | Art. 10, Art. 15 | MEASURE 2.7, MEASURE 2.10 | A.6.2.3, A.6.2.6 | A.5.34, A.8.3, A.8.12 | C1.1, C1.2, CC6.1, CC6.6, CC6.7, CC9.2 |
| 6.9 | Prompt injection | Instructions hidden in user input, documents or tool results cannot take control of the system. | EVAL_ADVERSARIAL_V1, EVAL_SAFETY_LEXICAL_V1 | Art. 14, Art. 15 | MEASURE 2.7 | A.6.2.3, A.6.2.6 | A.8.25, A.8.28, A.8.29 | CC6.6, CC6.7, CC7.1, CC8.1, PI1.3 |
| 6.10 | Output contains injection attacks | Model output is treated as untrusted and validated or encoded before it reaches other components. | EVAL_SAFETY_LEXICAL_V1 | Art. 15 | MEASURE 2.7 | A.6.2.3, A.6.2.6 | A.8.25, A.8.28, A.8.29 | CC6.6, CC6.7, CC7.1, CC8.1, PI1.3 |
| 6.11 | Considerations for AI systems | Data given to the system is limited to reduce impact, unwanted model behaviour in operation (including agent actions) is governed and contained, and the provenance of the system and its data is recorded. | — | Art. 10, Art. 12, Art. 14, Art. 15 | GOVERN 3.2, MEASURE 2.7 | A.7.5 | A.8.6, A.8.15, A.8.16 | A1.1, CC6.1, CC6.2, CC6.3, CC7.2 |
| 7.2 | Conflicting interactions of mitigations | Mitigations are checked for side effects on one another, and the trade-offs are recorded. | — | Art. 9 | MEASURE 1.2, MANAGE 1.3 | Clause 6.1.3 | — | CC5.1 |
| 7.3 | Continuity of mitigations across the AI life cycle | Mitigations stay in place from design through operation, retraining and retirement. | — | Art. 9, Art. 15 | GOVERN 1.7, MANAGE 4.1 | Clause 8.1, A.6.2.6 | A.8.25, A.8.32 | CC8.1 |
| 7.4 | Model and mitigation deterioration over time | Models and their defences are re-tested on a schedule, because both lose effect as data and attacks change. | — | Art. 15, Art. 72 | MEASURE 2.4, MEASURE 3.1 | Clause 9.1, A.6.2.6 | A.5.24, A.5.25, A.5.26, A.5.27, A.5.28, A.8.16 | CC7.2, CC7.3, CC7.4, CC7.5 |
| 7.5 | Logging and monitoring | Inputs, outputs, tool calls and query patterns are logged and watched for signs of attack, and alerts feed the incident process. | event_log_evidence (probe) | Art. 12, Art. 26, Art. 72, Art. 73 | MEASURE 2.4, MANAGE 4.1 | A.6.2.6, A.6.2.8 | A.5.24, A.5.25, A.5.26, A.5.27, A.5.28, A.8.15, A.8.16 | CC7.2, CC7.3, CC7.4, CC7.5 |
| 7.6 | Development environment protection | Training pipelines, datasets and model files are protected against unauthorised access and change. | — | Art. 15 | MEASURE 2.7 | A.4.4 | A.8.4, A.8.31 | CC6.1, CC8.1 |
| 7.7 | Malicious input detection and filtering | Malicious, adversarial or out-of-range inputs are detected and filtered, in addition to access control rather than instead of it. | — | Art. 15 | MEASURE 2.7 | — | A.8.26 | CC6.6 |
| 7.8 | Throttling model use | Rate and volume limits slow down query-based attacks and resource exhaustion. | rate_limiting_config (probe) | Art. 15 | MEASURE 2.7 | — | A.8.6, A.8.15, A.8.16 | A1.1, CC6.1, CC6.2, CC6.3, CC7.2 |
| 7.9 | Optimising the size of the model | Model size is matched to the task, which limits attack surface and memorisation of training data. | — | — | MEASURE 2.7 | — | — | — |
| B.2 | Denial-of-service attacks | Expensive or flooding inputs cannot exhaust the system; quotas and resource monitoring are in place. | rate_limiting_config (probe) | Art. 15 | MEASURE 2.7 | A.4.5 | A.8.6, A.8.15, A.8.16 | A1.1, CC6.1, CC6.2, CC6.3, CC7.2 |
| B.3 | Supply chain attacks | Compromised models, datasets, libraries or model hubs are considered and checked for. | ai_supply_chain_pins (probe) | Art. 15, Art. 25 | GOVERN 6.1, MAP 4.1, MANAGE 3.2 | A.10.3 | A.5.19, A.5.20, A.5.21, A.5.22, A.5.23, A.8.8 | CC6.8, CC7.1, CC9.1, CC9.2 |
| B.4 | Backdoor attacks | Models, especially third-party ones, are checked for hidden triggers before use. | — | Art. 15, Art. 25 | MEASURE 2.7, MANAGE 3.2 | — | A.5.21, A.8.30, A.8.32 | CC6.8, CC8.1, CC9.2 |
| B.5 | Direct model theft | Model weights are protected in storage and in use by access control and encryption. | — | Art. 15, Art. 55 | MEASURE 2.7 | — | A.8.3, A.8.16 | CC6.1, CC6.2, CC6.3, CC7.2 |
| B.6 | Direct training data leak | Training datasets are protected by access control, encryption, minimisation and de-identification. | — | Art. 10 | MEASURE 2.10 | A.7.2 | A.8.3, A.8.11, A.8.12 | C1.1, C1.2, CC6.1, CC6.2, CC6.3, CC7.2 |
| B.7 | Model input leak | Prompts and other inputs sent to the model stay confidential, including towards hosted model providers. | — | Art. 15 | MEASURE 2.10 | A.10.3 | A.5.34, A.8.3, A.8.12 | C1.1, C1.2, CC6.1, CC6.6, CC6.7, CC9.2 |

## ISO/IEC 27001:2022

Key `ISO_IEC_27001`. Attestation-led: every row reads Unverified until attested.

| Id | Heading | What we look for | Checks | EU AI Act | Linked from |
|---|---|---|---|---|---|
| Clause 4.1 | Understanding the organization and its context | Evidence that a written analysis of the inside and outside factors shaping the security programme exists and is refreshed when circumstances change. | — | — | — |
| Clause 4.2 | Understanding the needs and expectations of interested parties | Evidence that a register of stakeholders and their security, legal and contractual expectations exists, with an owner who keeps it current. | — | — | — |
| Clause 4.3 | Determining the scope of the information security management system | Evidence that a signed scope statement names the sites, services, systems and interfaces the programme covers and says what is excluded. | — | — | — |
| Clause 4.4 | Information security management system | Evidence that the security programme runs as a defined set of processes with owners, and is reviewed and tuned over time. | — | — | — |
| Clause 5.1 | Leadership and commitment | Evidence that senior leaders back the programme in practice: approved budget, minuted decisions, and security aims tied to business plans. | — | — | — |
| Clause 5.2 | Policy | Evidence that a security policy signed by senior leaders exists, staff have received it, and outsiders can obtain it where relevant. | — | — | — |
| Clause 5.3 | Organizational roles, responsibilities and authorities | Evidence that a RACI chart or role descriptions assign security duties to named roles, with a set route for reporting performance to senior leaders. | — | — | — |
| Clause 6.1.1 | General | Evidence that a documented list of risks and opportunities to the programme exists, with planned actions and a way of checking whether they worked. | — | — | — |
| Clause 6.1.2 | Information security risk assessment | Evidence that a written risk method and criteria exist, and a risk register shows assessed risks, each with a scored rating and a named owner. | — | Art. 9 | — |
| Clause 6.1.3 | Information security risk treatment | Evidence that a risk treatment plan and Statement of Applicability exist, control choices are justified, and owners accepted residual risk in writing. | — | Art. 9 | — |
| Clause 6.2 | Information security objectives and planning to achieve them | Evidence that dated, measurable security targets exist with owners, resources and a schedule, plus a record of progress against them. | — | — | — |
| Clause 6.3 | Planning of changes | Evidence that proposed changes to the security programme go through a planning step, with a record of what changes and who approved it, before rollout. | — | — | — |
| Clause 7.1 | Resources | Evidence that budgets, staffing and tooling for the programme are defined, approved and reviewed against what it needs. | — | — | — |
| Clause 7.2 | Competence | Evidence that the skills needed for security roles are defined, and training, qualification or experience records show each role holder meets them. | — | Art. 4 | — |
| Clause 7.3 | Awareness | Evidence that staff can show they know the security policy and their part in it, for example through induction records, quizzes or sign-offs. | — | — | — |
| Clause 7.4 | Communication | Evidence that a communication plan sets out which security topics go to whom, when and by what channel, and that the messages were actually sent. | — | — | — |
| Clause 7.5 | Documented information | Evidence that required documents sit in a controlled repository with versions, approvals, owners, access limits and retention rules. | — | Art. 11, Art. 17 | — |
| Clause 8.1 | Operational planning and control | Evidence that procedures and criteria for running risk treatment exist, outsourced work is controlled, and changes were reviewed before going live. | — | — | — |
| Clause 8.2 | Information security risk assessment | Evidence that dated risk assessment reports exist for each planned cycle and after major change, and are kept as records. | — | Art. 9 | — |
| Clause 8.3 | Information security risk treatment | Evidence that the treatment plan is being carried out, shown by completed actions, implementation records and retained results. | — | Art. 9 | — |
| Clause 9.1 | Monitoring, measurement, analysis and evaluation | Evidence that a measurement plan names the metrics, methods, timing and owners, and that dated analyses of the results exist. | — | — | — |
| Clause 9.2 | Internal audit | Evidence that an audit schedule, scope and criteria exist, audits were done by impartial auditors, and reports reached the relevant managers. | — | — | — |
| Clause 9.3 | Management review | Evidence that minutes of management reviews held on schedule show the standard inputs were covered and decisions on changes were recorded. | — | — | — |
| Clause 10.1 | Continual improvement | Evidence that improvement actions are tracked from review and audit findings through to completion, with a record of their measured effect. | — | — | — |
| Clause 10.2 | Nonconformity and corrective action | Evidence that a corrective action log shows each nonconformity, its root cause, the fix, and a check that the fix worked. | — | — | — |
| A.5.1 | Policies for information security | Evidence that approved security policies exist, dated and versioned, with staff acknowledgements and a log of the last review. | — | — | ISO_IEC_27090, SOC_2, NIS2, DORA, EIOPA_AI, GDPR |
| A.5.2 | Information security roles and responsibilities | Evidence that a responsibility matrix or role descriptions give each security task a named owner. | — | — | ISO_IEC_27090, SOC_2, NIS2, DORA, EBA, EIOPA_AI, GDPR |
| A.5.3 | Segregation of duties | Evidence that a conflicting-duties analysis exists, with role splits in system set-ups or compensating checks where a split is impossible. | — | — | SOC_2, NIS2, DORA |
| A.5.4 | Management responsibilities | Evidence that managers brief their teams on security rules and follow up on lapses, shown by briefing records, sign-offs or review actions. | — | — | SOC_2, NIS2, DORA, EBA |
| A.5.5 | Contact with authorities | Evidence that a contact list for regulators, police and emergency services is maintained, with the date it was last checked. | — | — | SOC_2, NIS2, DORA, GDPR, CRA |
| A.5.6 | Contact with special interest groups | Evidence that security staff hold memberships of, or attend, named forums, and that what they learn is shared internally. | — | — | DORA, CRA |
| A.5.7 | Threat intelligence | Evidence that threat feeds or advisories are collected, triaged by a named person, and traceably used in risk or control decisions. | — | — | ISO_IEC_27090, SOC_2, NIS2, DORA, ETSI_EN_304_223 |
| A.5.8 | Information security in project management | Evidence that project templates or gate checklists include security steps, with completed examples from recent projects. | — | — | SOC_2, GDPR, ETSI_EN_304_223 |
| A.5.9 | Inventory of information and other associated assets | Evidence that an asset register lists information and the systems that hold it, each with a named owner and a review date. | — | — | SOC_2, NIS2, DORA, EBA, GDPR, CRA, ETSI_EN_304_223 |
| A.5.10 | Acceptable use of information and other associated assets | Evidence that written rules on permitted handling of company information and devices exist and users have signed to accept them. | — | — | NIS2 |
| A.5.11 | Return of assets | Evidence that leaver and mover checklists include handing back devices, badges and media, with completed returns on file. | — | — | NIS2 |
| A.5.12 | Classification of information | Evidence that a scheme with defined sensitivity levels exists and that sampled records or systems carry a level. | — | — | ISO_IEC_27090, SOC_2, NIS2, DORA, GDPR, ETSI_EN_304_223 |
| A.5.13 | Labelling of information | Evidence that a labelling guide exists and sampled documents or data stores visibly carry the markings it requires. | — | — | SOC_2, NIS2 |
| A.5.14 | Information transfer | Evidence that transfer rules or agreements cover each channel in use (email, file share, courier, API) and sampled transfers follow them. | — | — | SOC_2, NIS2, DORA, GDPR, CRA, ETSI_EN_304_223 |
| A.5.15 | Access control | Evidence that a written permissions policy and system permission settings show who may use what, justified by role or business need. | — | — | ISO_IEC_27090, SOC_2, NIS2, DORA, GDPR, CRA, ETSI_EN_304_223 |
| A.5.16 | Identity management | Evidence that joiner, mover and leaver records show accounts being created, changed and removed through a managed lifecycle. | — | — | SOC_2, NIS2, CRA |
| A.5.17 | Authentication information | Evidence that credential issuance and reset follow a documented procedure, and password or key standards are enforced in system settings. | — | — | SOC_2, NIS2 |
| A.5.18 | Access rights | Evidence that rights are granted on approved requests, periodically recertified, and removed on role change, shown by tickets and review sign-offs. | — | — | SOC_2, NIS2, DORA, ETSI_EN_304_223 |
| A.5.19 | Information security in supplier relationships | Evidence that supplier risk assessments and a supplier security policy exist, with suppliers tiered by the risk they bring. | — | Art. 25 | ISO_IEC_27090, SOC_2, NIS2, DORA, EBA, EIOPA_AI, GDPR, CRA, ETSI_EN_304_223 |
| A.5.20 | Addressing information security within supplier agreements | Evidence that sampled supplier contracts contain security clauses fitted to what each supplier does for the organisation. | — | Art. 25 | ISO_IEC_27090, SOC_2, NIS2, DORA, EBA, GDPR, ETSI_EN_304_223 |
| A.5.21 | Managing information security in the ICT supply chain | Evidence that upstream components and sub-suppliers, including AI models and libraries, are inventoried with pinned versions and checked for risk. | ai_supply_chain_pins (probe) | Art. 25 | ISO_IEC_27090, SOC_2, NIS2, DORA, EBA, CRA, ETSI_EN_304_223 |
| A.5.22 | Monitoring, review and change management of supplier services | Evidence that supplier performance reviews, audit reports or certifications are checked on a schedule and service changes pass through approval. | — | Art. 25 | ISO_IEC_27090, SOC_2, NIS2, DORA, EBA, GDPR, ETSI_EN_304_223 |
| A.5.23 | Information security for use of cloud services | Evidence that a cloud policy and per-service assessments exist, covering data protection, shared responsibilities and how to exit. | — | Art. 25 | ISO_IEC_27090, SOC_2, NIS2, DORA, EBA, ETSI_EN_304_223 |
| A.5.24 | Information security incident management planning and preparation | Evidence that an incident response plan names roles and steps, is approved, and has been exercised or used, with participants aware of it. | — | Art. 73 | ISO_IEC_27090, SOC_2, NIS2, DORA, GDPR, CRA, ETSI_EN_304_223 |
| A.5.25 | Assessment and decision on information security events | Evidence that triage records show each reported event rated against set criteria, with the call on whether it is an incident written down. | — | Art. 73 | ISO_IEC_27090, SOC_2, NIS2, DORA, GDPR, CRA |
| A.5.26 | Response to information security incidents | Evidence that closed incident tickets follow the documented steps from containment to recovery, with timestamps and responders. | — | Art. 73 | ISO_IEC_27090, SOC_2, NIS2, DORA, GDPR, CRA, ETSI_EN_304_223 |
| A.5.27 | Learning from information security incidents | Evidence that post-incident reviews exist and lead to tracked changes in controls, procedures or training. | — | Art. 73 | ISO_IEC_27090, SOC_2, NIS2, DORA, GDPR |
| A.5.28 | Collection of evidence | Evidence that an evidence-handling procedure exists and case files show logs or disk images preserved with chain-of-custody notes. | — | Art. 73 | ISO_IEC_27090, SOC_2, NIS2, DORA, GDPR |
| A.5.29 | Information security during disruption | Evidence that continuity plans state which security measures must hold during a disruption, and exercises or real events confirmed it. | — | — | SOC_2, NIS2, DORA, EBA |
| A.5.30 | ICT readiness for business continuity | Evidence that recovery objectives for ICT services are set and test reports show failover or restore results measured against them. | — | — | SOC_2, NIS2, DORA, EBA, EIOPA_AI, ETSI_EN_304_223 |
| A.5.31 | Legal, statutory, regulatory and contractual requirements | Evidence that a register of legal and contractual obligations exists, has owners, and shows updates when laws or contracts change. | — | — | SOC_2, NIS2, GDPR, CRA |
| A.5.32 | Intellectual property rights | Evidence that software licence records and a permitted-software list show licences match actual use, with rules on third-party material. | — | — | NIS2 |
| A.5.33 | Protection of records | Evidence that a retention schedule and storage safeguards exist for records, with integrity and permission protections visible in the systems holding them. | — | — | SOC_2, EBA, EIOPA_AI, CRA |
| A.5.34 | Privacy and protection of PII | Evidence that a privacy programme exists with a named lead, a record of personal data processing, and working procedures for legal duties. | — | — | ISO_IEC_27090, SOC_2, EBA, EIOPA_AI, GDPR, CRA, ETSI_EN_304_223 |
| A.5.35 | Independent review of information security | Evidence that independent reviews, internal or external, are reported on a schedule and after major change, with actions followed up. | — | — | SOC_2, NIS2, DORA, EBA, GDPR, ETSI_EN_304_223 |
| A.5.36 | Compliance with policies, rules and standards for information security | Evidence that managers' periodic checks of their areas against policy are recorded, with findings and corrections. | — | — | SOC_2, NIS2, DORA |
| A.5.37 | Documented operating procedures | Evidence that run books or operating procedures exist for key systems, are version controlled, and are reachable by the people who use them. | — | Art. 11, Art. 17 | SOC_2, EIOPA_AI, CRA, ETSI_EN_304_223 |
| A.6.1 | Screening | Evidence that screening records (identity, references, qualifications, checks the law permits) exist for sampled hires, scaled to role risk. | — | — | SOC_2, NIS2, DORA |
| A.6.2 | Terms and conditions of employment | Evidence that sampled employment contracts or policies signed at hiring state the person's security duties. | — | — | SOC_2, NIS2 |
| A.6.3 | Information security awareness, education and training | Evidence that a training plan, course content and completion records show role-appropriate security awareness, repeated periodically. | — | Art. 4 | SOC_2, NIS2, DORA, EIOPA_AI, ETSI_EN_304_223 |
| A.6.4 | Disciplinary process | Evidence that a documented disciplinary procedure covers security breaches and that staff were told about it. | — | — | SOC_2, NIS2 |
| A.6.5 | Responsibilities after termination or change of employment | Evidence that exit procedures remind leavers and movers of continuing duties such as confidentiality, with signed acknowledgements. | — | — | NIS2 |
| A.6.6 | Confidentiality or non-disclosure agreements | Evidence that signed secrecy agreements are on file for staff and contractors, using a template that legal has reviewed. | — | — | SOC_2 |
| A.6.7 | Remote working | Evidence that a remote-work policy and technical settings (VPN, encryption, device rules) apply to people working off-site. | — | — | — |
| A.6.8 | Information security event reporting | Evidence that a reporting channel exists, staff know it, and logged reports show events being raised and passed to incident handling. | — | — | SOC_2, NIS2, DORA, GDPR, CRA, ETSI_EN_304_223 |
| A.7.1 | Physical security perimeters | Evidence that site plans or zone documents define secured areas, with physical barriers that match them. | — | — | SOC_2, NIS2 |
| A.7.2 | Physical entry | Evidence that badge, lock or visitor logs show entry to secured areas is restricted and recorded. | — | — | SOC_2, NIS2 |
| A.7.3 | Securing offices, rooms and facilities | Evidence that site security design reviews or surveys cover rooms and offices holding sensitive assets, with fixes tracked. | — | — | SOC_2, NIS2 |
| A.7.4 | Physical security monitoring | Evidence that cameras, alarms or guard rounds cover sensitive areas, with retained footage or logs and reviewed alerts. | — | — | SOC_2, NIS2 |
| A.7.5 | Protecting against physical and environmental threats | Evidence that a risk assessment of fire, flood, power and similar hazards exists for key sites, with protective measures installed. | — | — | SOC_2, NIS2 |
| A.7.6 | Working in secure areas | Evidence that written rules for working in secure areas exist and are displayed or briefed, such as escort or no-photography rules. | — | — | — |
| A.7.7 | Clear desk and clear screen | Evidence that a clear-desk and screen-lock rule exists, enforced by settings, with spot-check results on file. | — | — | — |
| A.7.8 | Equipment siting and protection | Evidence that equipment locations were chosen with hazards and onlookers in mind, shown by layouts or inspection records. | — | — | SOC_2 |
| A.7.9 | Security of assets off-premises | Evidence that rules and records cover devices taken off site, such as loan registers, encryption settings and travel guidance. | — | — | — |
| A.7.10 | Storage media | Evidence that media are tracked from purchase to destruction, with handling rules by sensitivity level and logs of transport or destruction. | — | — | SOC_2 |
| A.7.11 | Supporting utilities | Evidence that UPS, generator, cooling and similar installations serve critical areas, with maintenance and test records. | — | — | SOC_2, NIS2 |
| A.7.12 | Cabling security | Evidence that power and network cable runs are protected, shown by inspection records, labelling or ducting on critical routes. | — | — | — |
| A.7.13 | Equipment maintenance | Evidence that maintenance schedules and service records exist for key equipment, performed by approved people. | — | — | SOC_2, NIS2 |
| A.7.14 | Secure disposal or re-use of equipment | Evidence that disposal and reuse records show data wiped or media destroyed, with certificates or checklists for each item. | — | — | SOC_2, CRA, ETSI_EN_304_223 |
| A.8.1 | User endpoint devices | Evidence that endpoint policy settings (encryption, patching, screen lock, remote wipe) are enforced and device management reports show coverage. | — | — | — |
| A.8.2 | Privileged access rights | Evidence that a list of privileged accounts exists, approval for each is recorded, and elevated rights are reviewed and time-limited. | — | — | ISO_IEC_27090, SOC_2, NIS2, DORA, ETSI_EN_304_223 |
| A.8.3 | Information access restriction | Evidence that permission settings in applications and data stores match the written rules, shown by configuration exports or review samples. | — | — | ISO_IEC_27090, SOC_2, NIS2, DORA, ETSI_EN_304_223 |
| A.8.4 | Access to source code | Evidence that repository permissions show who can read or change source code, limited to those who need it, with review records. | — | — | ISO_IEC_27090 |
| A.8.5 | Secure authentication | Evidence that login settings show strong sign-in, such as multi-factor, matched to the sensitivity of each system. | — | — | ISO_IEC_27090, SOC_2, NIS2, DORA, CRA |
| A.8.6 | Capacity management | Evidence that capacity reports, thresholds and growth forecasts exist, and actions follow when thresholds are neared. | — | — | ISO_IEC_27090, SOC_2, DORA, CRA |
| A.8.7 | Protection against malware | Evidence that endpoint and gateway anti-malware tools are deployed, updating and reporting, with awareness material for users. | — | — | SOC_2, NIS2 |
| A.8.8 | Management of technical vulnerabilities | Evidence that scan results, patch records and exposure assessments show weaknesses found, rated and addressed within set timeframes. | — | Art. 15 | ISO_IEC_27090, SOC_2, NIS2, DORA, EIOPA_AI, CRA, ETSI_EN_304_223 |
| A.8.9 | Configuration management | Evidence that secure baselines exist, configuration is tracked in tooling or records, and drift from the baseline is detected and reviewed. | — | — | SOC_2, NIS2, CRA, ETSI_EN_304_223 |
| A.8.10 | Information deletion | Evidence that deletion rules, jobs or scripts exist and logs or certificates show data removed once its need ended. | — | — | SOC_2, GDPR, CRA, ETSI_EN_304_223 |
| A.8.11 | Data masking | Evidence that masking, pseudonymisation or similar techniques are applied where needed, shown by configuration or sample data views. | — | — | ISO_IEC_27090, GDPR, CRA |
| A.8.12 | Data leakage prevention | Evidence that leak-prevention tooling or equivalent rules watch key channels, with alerts handled and rules tuned. | — | — | ISO_IEC_27090, SOC_2 |
| A.8.13 | Information backup | Evidence that a backup policy, job reports and restore test results exist, showing backups run and can actually be restored. | — | Art. 15 | SOC_2, NIS2, DORA, GDPR, ETSI_EN_304_223 |
| A.8.14 | Redundancy of information processing facilities | Evidence that architecture documents or failover tests show critical services have duplicate components to meet availability targets. | — | Art. 15 | SOC_2, NIS2, DORA, CRA |
| A.8.15 | Logging | Evidence that logging settings, sample logs and retention rules show key events recorded, protected from tampering and reviewed. | event_log_evidence (probe) | Art. 12 | ISO_IEC_27090, SOC_2, NIS2, DORA, CRA, ETSI_EN_304_223 |
| A.8.16 | Monitoring activities | Evidence that alerting rules, dashboards and triage records show unusual activity being detected and followed up. | event_log_evidence (probe) | Art. 12, Art. 72 | ISO_IEC_27090, SOC_2, NIS2, DORA, CRA, ETSI_EN_304_223 |
| A.8.17 | Clock synchronization | Evidence that systems are set to sync with approved time sources, shown by configuration exports or drift checks. | — | — | NIS2 |
| A.8.18 | Use of privileged utility programs | Evidence that powerful admin utilities are limited to approved people, with usage logged and reviewed. | — | — | — |
| A.8.19 | Installation of software on operational systems | Evidence that an installation procedure and allow-list or approval records show only approved software reaches live systems. | — | — | SOC_2 |
| A.8.20 | Networks security | Evidence that network diagrams, device hardening standards and monitoring show networks are protected and administered by authorised people. | — | — | SOC_2, NIS2, DORA, CRA, ETSI_EN_304_223 |
| A.8.21 | Security of network services | Evidence that requirements for network services, such as security features and service levels, are documented and checked against provider reports. | — | — | SOC_2 |
| A.8.22 | Segregation of networks | Evidence that network diagrams and firewall or VLAN rules show separate zones for different users, services and sensitivity levels. | — | — | SOC_2, NIS2, DORA |
| A.8.23 | Web filtering | Evidence that web filtering or proxy rules block risky categories, with block reports or policy exports on file. | — | — | SOC_2 |
| A.8.24 | Use of cryptography | Evidence that a cryptography standard and key lifecycle records exist, with sampled systems using the approved algorithms and key handling. | — | — | SOC_2, NIS2, DORA, GDPR, CRA, ETSI_EN_304_223 |
| A.8.25 | Secure development life cycle | Evidence that a written secure development lifecycle exists and sampled projects show its security activities done at each phase. | — | Art. 15 | ISO_IEC_27090, SOC_2, NIS2, GDPR, CRA |
| A.8.26 | Application security requirements | Evidence that requirement documents for new or bought applications include security requirements, signed off before build or purchase. | — | Art. 15 | ISO_IEC_27090, SOC_2, CRA |
| A.8.27 | Secure system architecture and engineering principles | Evidence that secure design principles are documented, and design or architecture reviews show them applied to systems. | — | Art. 15 | ISO_IEC_27090, GDPR, CRA, ETSI_EN_304_223 |
| A.8.28 | Secure coding | Evidence that a written secure coding standard exists and code is checked against it, through reviews or automated analysis. | — | Art. 15 | ISO_IEC_27090, SOC_2, CRA, ETSI_EN_304_223 |
| A.8.29 | Security testing in development and acceptance | Evidence that security test plans and results (scans, penetration tests, acceptance sign-offs) exist for releases, with findings fixed or accepted. | — | Art. 15 | ISO_IEC_27090, SOC_2, NIS2, DORA, EIOPA_AI, CRA, ETSI_EN_304_223 |
| A.8.30 | Outsourced development | Evidence that contracts and oversight records for external developers cover security requirements, review or testing rights, and delivery checks. | — | Art. 25 | ISO_IEC_27090, NIS2 |
| A.8.31 | Separation of development, test and production environments | Evidence that separate environments exist for build, test and live, with different credentials and restricted promotion paths between them. | — | — | ISO_IEC_27090, SOC_2, NIS2, ETSI_EN_304_223 |
| A.8.32 | Change management | Evidence that change tickets show request, risk review, approval, testing and rollback planning before changes reach live systems. | — | Art. 17 | ISO_IEC_27090, SOC_2, NIS2, DORA, CRA, ETSI_EN_304_223 |
| A.8.33 | Test information | Evidence that test data is chosen or scrambled, protected, and removed afterwards, with rules against copying live personal data. | — | — | SOC_2, NIS2 |
| A.8.34 | Protection of information systems during audit testing | Evidence that test plans for audits on live systems were agreed with system owners beforehand, with limits on scope and timing. | — | — | NIS2, DORA |

## SOC 2 Trust Services Criteria

Key `SOC_2`. Attestation-led: every row reads Unverified until attested.

| Id | Heading | What we look for | Checks | EU AI Act | ISO/IEC 27001 Annex A |
|---|---|---|---|---|---|
| CC1.1 | Integrity and ethical values | Evidence that a code of conduct exists, staff attest to it, and records show breaches were investigated and acted on. | — | — | A.5.4, A.6.2, A.6.4 |
| CC1.2 | Board independence and oversight of internal control | Evidence that board charters, independence statements, skills matrices and minutes show the board reviews how internal controls perform. | — | — | A.5.4, A.5.35 |
| CC1.3 | Structures, reporting lines and responsibilities | Evidence that organisation charts, role descriptions and a delegation of authority document set out who reports to whom and who decides what. | — | Art. 17 | A.5.2, A.5.3 |
| CC1.4 | Attracting, developing and retaining competent people | Evidence that hiring standards, training plans, performance reviews and succession records show the organisation staffs and develops the skills it needs. | — | Art. 4 | A.6.1, A.6.3 |
| CC1.5 | Accountability for internal control duties | Evidence that job objectives, performance reviews and disciplinary records tie people's evaluation to their control duties. | — | — | A.5.4, A.6.4 |
| CC2.1 | Quality information to support internal control | Evidence that data flow diagrams, an asset inventory and data quality checks show which information feeds controls and where it comes from. | — | — | A.5.9, A.5.12 |
| CC2.2 | Internal communication of objectives and duties | Evidence that policies, staff notices, training and an incident reporting route reach employees, with board briefings on control matters. | — | — | A.5.1, A.6.3, A.6.8 |
| CC2.3 | Communication with external parties | Evidence that customer-facing documents, contracts, a status page and a feedback or complaint channel inform outside parties about the service. | — | — | A.5.5, A.6.8 |
| CC3.1 | Clear objectives so risks can be assessed | Evidence that documented business and service objectives, with risk tolerances, are specific enough to be used in the risk assessment. | — | — | A.5.1, A.5.31 |
| CC3.2 | Risk identification and analysis | Evidence that a risk register from a recurring assessment lists risks to objectives, rates them, names owners and records chosen responses. | — | Art. 9 | A.5.7, A.8.8 |
| CC3.3 | Fraud risk consideration | Evidence that the risk assessment includes a fraud section covering pressures, opportunities and IT misuse scenarios. | — | — | A.5.3 |
| CC3.4 | Assessing changes that affect internal control | Evidence that risk reviews are triggered by change, such as new products, leaders, vendors or threats, with records of what was reassessed. | — | Art. 9 | A.5.7, A.8.32 |
| CC4.1 | Ongoing and separate control evaluations | Evidence that a monitoring plan, internal audit or self-assessment reports, and external reviews show controls are tested regularly. | — | — | A.5.35, A.5.36 |
| CC4.2 | Reporting and correcting control deficiencies | Evidence that a deficiency log with severity, owner and due date exists, and management or board reports show escalation and closure. | — | — | A.5.35, A.5.36 |
| CC5.1 | Control activities that reduce risk | Evidence that a control matrix links each risk to the controls that reduce it, including duty splits where needed. | — | — | A.5.1, A.5.37 |
| CC5.2 | General controls over technology | Evidence that general IT controls, such as infrastructure management, security administration and system development standards, are documented and operated. | — | — | A.8.9, A.8.25 |
| CC5.3 | Controls deployed through policies and procedures | Evidence that approved policies and matching procedures have owners, are reviewed on schedule, and are applied by staff. | — | Art. 17 | A.5.1, A.5.37 |
| CC6.1 | Logical access security over protected assets | Evidence that system configurations show protected assets sit behind enforced sign-in, role permissions and encryption, backed by an asset inventory. | — | Art. 15 | A.5.12, A.5.15, A.5.16, A.5.17, A.8.2, A.8.3, A.8.5, A.8.24 |
| CC6.2 | User registration and credential issuance | Evidence that access request and approval tickets exist before accounts are created, and that deactivation records follow departures. | — | — | A.5.16, A.5.18 |
| CC6.3 | Granting, changing and removing access | Evidence that role definitions, approval records and periodic access reviews show rights follow job need and are removed or changed promptly. | — | — | A.5.3, A.5.15, A.5.18, A.8.2 |
| CC6.4 | Physical access to facilities and assets | Evidence that badge logs, visitor records, lock configurations and data-centre access lists show only approved people enter sensitive areas. | — | — | A.7.1, A.7.2, A.7.3, A.7.4 |
| CC6.5 | Secure disposal of assets and media | Evidence that asset retirement records, wipe or destruction certificates and media logs show data was unrecoverable before equipment left control. | — | — | A.7.10, A.7.14, A.8.10 |
| CC6.6 | Protection against threats from outside the system boundary | Evidence that firewall rules, network diagrams, external scans and intrusion prevention settings show the system edge is defended. | — | Art. 15 | A.8.20, A.8.21, A.8.22, A.8.23 |
| CC6.7 | Controls over moving and transmitting information | Evidence that transfer tooling, encryption-in-transit settings and removable media rules show data movement is restricted and protected. | — | — | A.5.14, A.7.10, A.8.12, A.8.24 |
| CC6.8 | Preventing and detecting malicious software | Evidence that endpoint protection, email and web filtering, and software allow-lists are deployed, with alert and response records. | — | Art. 15 | A.8.7, A.8.16, A.8.19 |
| CC7.1 | Detecting vulnerabilities and risky configuration changes | Evidence that vulnerability scan reports, configuration drift alerts and patch records show weaknesses and risky changes are detected. | — | Art. 15 | A.8.8, A.8.9, A.8.16 |
| CC7.2 | Monitoring systems for anomalies | Evidence that log collection, alert rules and a reviewed alert queue show unusual system activity is noticed and investigated. | event_log_evidence (probe) | Art. 12, Art. 72 | A.8.15, A.8.16 |
| CC7.3 | Evaluating security events as incidents | Evidence that security alert tickets show each event triaged against defined criteria, with the incident or not-incident decision recorded. | — | Art. 73 | A.5.24, A.5.25, A.6.8 |
| CC7.4 | Incident response program | Evidence that an incident response plan exists and incident records show containment, fixes, stakeholder updates and a closing review. | — | Art. 73 | A.5.24, A.5.26, A.5.27, A.5.28 |
| CC7.5 | Recovery from security incidents | Evidence that recovery runbooks, restore or failover test results and post-incident reviews show the organisation can return to normal service. | — | Art. 73 | A.5.26, A.5.29, A.5.30, A.8.13 |
| CC8.1 | Change management | Evidence that change tickets and pipeline records show each change designed, tested, approved and released through a set process, including urgent fixes. | — | Art. 15, Art. 17 | A.5.8, A.8.9, A.8.25, A.8.26, A.8.29, A.8.31, A.8.32, A.8.33 |
| CC9.1 | Risk mitigation for business disruption | Evidence that a business continuity plan, impact analysis, insurance cover and exercise results exist for disruptions. | — | — | A.5.29, A.5.30, A.8.13, A.8.14 |
| CC9.2 | Vendor and business partner risk | Evidence that vendor inventories, due diligence files, contracts and periodic reviews show supplier risk is evaluated and followed up. | — | Art. 25 | A.5.19, A.5.20, A.5.21, A.5.22, A.5.23 |
| A1.1 | Capacity management | Evidence that capacity dashboards, utilisation thresholds and demand forecasts exist, with scaling actions taken ahead of shortfalls. | — | — | A.8.6 |
| A1.2 | Environmental protections, backup and recovery infrastructure | Evidence that backup job reports, environmental protection records (power, cooling, fire) and recovery environment documentation support availability. | — | Art. 15 | A.5.30, A.7.5, A.7.8, A.7.11, A.7.13, A.8.13, A.8.14 |
| A1.3 | Testing of recovery plans | Evidence that dated disaster recovery or restore test reports exist, with results compared to targets and fixes tracked. | — | Art. 15 | A.5.30, A.8.13 |
| C1.1 | Identifying and maintaining confidential information | Evidence that a data inventory or classification marks confidential items, with handling rules, permission limits and retention periods in place. | — | — | A.5.9, A.5.12, A.5.13, A.6.6 |
| C1.2 | Disposal of confidential information | Evidence that disposal records, deletion logs or destruction certificates show confidential data removed when retention ended. | — | — | A.7.10, A.7.14, A.8.10 |
| PI1.1 | Processing objectives and information specifications | Evidence that service descriptions, data definitions and specifications state what is processed and expected, and are shared with users. | — | — | A.5.37, A.8.26 |
| PI1.2 | Controls over system inputs | Evidence that input validation rules, reconciliation checks and input logs show incoming data is checked for completeness and accuracy. | — | — | A.8.26, A.8.28 |
| PI1.3 | Controls over system processing | Evidence that processing controls such as job monitoring, error handling and authorisation checks show processing runs completely and accurately. | — | Art. 15 | A.8.26, A.8.29 |
| PI1.4 | Controls over system outputs | Evidence that output reports, delivery logs and reconciliations show results reach the intended recipients complete and on time. | — | — | A.5.14, A.8.3 |
| PI1.5 | Controls over stored items | Evidence that integrity checks, backups and storage permissions show stored data stays complete, accurate and protected for its retention period. | — | — | A.5.33, A.8.13 |
| P1.1 | Privacy notice to data subjects | Evidence that a published privacy notice exists, with a version history showing it is updated and changes are communicated. | — | — | A.5.34 |
| P2.1 | Choice and consent | Evidence that consent and preference mechanisms, such as opt-in screens or settings, exist along with records of choices people made. | — | — | A.5.34 |
| P3.1 | Collection of personal information | Evidence that data collection points and forms are listed and checked against stated privacy purposes, so only needed data is gathered. | — | Art. 10 | A.5.34 |
| P3.2 | Explicit consent for sensitive information | Evidence that explicit consent capture, with an explanation of what refusal means, is built into collection flows and consent records are stored. | — | — | A.5.34 |
| P4.1 | Use limited to stated purposes | Evidence that a record of processing purposes and internal use restrictions shows data is applied only to the stated purposes. | — | — | A.5.34 |
| P4.2 | Retention of personal information | Evidence that a retention schedule for personal data exists and system settings or deletion jobs apply it. | — | — | A.5.33, A.5.34 |
| P4.3 | Secure disposal of personal information | Evidence that deletion or destruction logs show personal data removed securely once no longer required. | — | — | A.5.34, A.7.14, A.8.10 |
| P5.1 | Data subject access to their information | Evidence that a request-handling procedure, an identity verification step and a request log show people can obtain a copy of their data. | — | — | A.5.34 |
| P5.2 | Correction of personal information | Evidence that correction requests are logged and completed, with records of notices sent to third parties who hold the data. | — | — | A.5.34 |
| P6.1 | Disclosure to third parties with consent | Evidence that consent records are checked before data is shared externally, shown by sharing approvals or workflow gates. | — | — | A.5.14, A.5.34 |
| P6.2 | Record of authorised disclosures | Evidence that a disclosure log lists each approved sharing of personal data, with date, recipient and purpose. | — | — | A.5.33, A.5.34 |
| P6.3 | Record of unauthorised disclosures and breaches | Evidence that an incident or breach register records suspected and confirmed unauthorised disclosures, with dates, scope and handling. | — | — | A.5.28, A.5.33, A.5.34 |
| P6.4 | Privacy commitments from vendors and third parties | Evidence that vendor contracts contain privacy terms and that assessments, questionnaires or audit reports on those vendors are on file. | — | — | A.5.19, A.5.20, A.5.22, A.5.34 |
| P6.5 | Vendor duty to report unauthorised disclosures | Evidence that vendor agreements require prompt notice of suspected data exposure, with tested contact routes. | — | — | A.5.20, A.5.22 |
| P6.6 | Breach and incident notification | Evidence that a breach notification procedure and records of notices sent to individuals and regulators show affected parties are informed. | — | — | A.5.26, A.5.34 |
| P6.7 | Accounting of held and disclosed information | Evidence that a procedure and request log show individuals can obtain a summary of the data held and who it was shared with. | — | — | A.5.34 |
| P7.1 | Accuracy and quality of personal information | Evidence that data quality checks, update processes and user self-service corrections keep personal records accurate and current. | — | Art. 10 | A.5.34 |
| P8.1 | Privacy inquiries, complaints and compliance monitoring | Evidence that a complaint and inquiry log, resolution records and periodic privacy compliance reviews exist. | — | — | A.5.34, A.5.36 |

## NIS2 Directive (EU) 2022/2555

Key `NIS2`. Attestation-led: every row reads Unverified until attested.

| Id | Heading | What we look for | Checks | EU AI Act | ISO/IEC 27001 Annex A |
|---|---|---|---|---|---|
| Art. 20(1) | Governance: management approves and oversees the security measures | Evidence that the management body formally approves the cybersecurity risk-management measures, oversees how they are rolled out, and accepts accountability for them (the Implementing Regulation's annex 1.1, 1.2 and 2.3 add detail for digital-infrastructure entities). | — | Art. 17 | A.5.2, A.5.4 |
| Art. 20(2) | Governance: cybersecurity training for management bodies | Evidence that members of the management body take regular training that lets them judge cybersecurity risks and the organisation's practices, and that similar training is offered to staff. | — | — | A.6.3 |
| Art. 21(1) | Appropriate and proportionate cybersecurity risk-management measures | Evidence that technical, operational and organisational security measures are chosen in proportion to the organisation's risk exposure, size and incident impact, to protect its network and information systems and their users. | — | Art. 9, Art. 15 | A.5.1, A.5.36 |
| Art. 21(2)(a) | Policies on risk analysis and information system security | Evidence of a maintained risk-analysis process and an information-system security policy that management approves and reviews (Implementing Regulation annex 1 and 2). | — | Art. 9, Art. 15 | A.5.1, A.5.2, A.5.3, A.5.4, A.5.7, A.5.19, A.5.20, A.5.21, A.5.31, A.5.35, A.5.36, A.8.34 |
| Art. 21(2)(b) | Incident handling | Evidence of an incident-handling process covering monitoring and logging, reporting of events, assessment, response and post-incident review (Implementing Regulation annex 3). | — | Art. 26, Art. 73 | A.5.24, A.5.25, A.5.26, A.5.27, A.5.28, A.6.8, A.8.15, A.8.16, A.8.17 |
| Art. 21(2)(c) | Business continuity, backup, disaster recovery and crisis management | Evidence of business continuity, disaster recovery, backup and crisis-management plans that are kept current and recovery-tested (Implementing Regulation annex 4; annex 13 on utilities and physical threats also applies). | — | Art. 15 | A.5.26, A.5.29, A.5.30, A.7.11, A.8.13, A.8.14 |
| Art. 21(2)(d) | Supply chain security, including direct suppliers and service providers | Evidence that the security of suppliers and service providers is managed through a policy, a supplier directory and security terms in contracts (Implementing Regulation annex 5). | — | Art. 25 | A.5.19, A.5.20, A.5.21, A.5.22, A.8.30 |
| Art. 21(2)(e) | Security in systems acquisition, development, maintenance and vulnerabilities | Evidence of security requirements when buying or building systems, secure development, change and patch management, testing, network security and a vulnerability handling and disclosure process (Implementing Regulation annex 6). | — | Art. 15 | A.5.21, A.5.23, A.5.32, A.7.13, A.8.7, A.8.8, A.8.9, A.8.16, A.8.20, A.8.22, A.8.25, A.8.29, A.8.31, A.8.32, A.8.33, A.8.34 |
| Art. 21(2)(f) | Assessing the effectiveness of cybersecurity risk-management measures | Evidence of a routine for checking whether the security measures work, such as audits, testing and metrics, with results reported to management (Implementing Regulation annex 7). | — | Art. 9 | A.5.35, A.5.36 |
| Art. 21(2)(g) | Basic cyber hygiene practices and cybersecurity training | Evidence of staff awareness, basic cyber hygiene practices and role-appropriate security training (Implementing Regulation annex 8). | — | Art. 4 | A.6.3, A.8.7 |
| Art. 21(2)(h) | Cryptography and, where appropriate, encryption | Evidence of a policy that sets when and how cryptography and encryption are used, including key management (Implementing Regulation annex 9). | — | — | A.5.31, A.8.24 |
| Art. 21(2)(i) | Human resources security, access control and asset management | Evidence of staff vetting and leaver handling, access control with least privilege, and a classified asset inventory (Implementing Regulation annex 10, 11, 12 and 13); this one point bundles three topics and could be split. | — | — | A.5.9, A.5.10, A.5.11, A.5.12, A.5.13, A.5.15, A.5.16, A.5.17, A.5.18, A.6.1, A.6.2, A.6.4, A.6.5, A.7.1, A.7.2, A.7.3, A.7.4, A.7.5, A.8.2, A.8.3 |
| Art. 21(2)(j) | Multi-factor authentication and secured communications | Evidence that multi-factor or continuous authentication and secured voice, video, text and emergency communications are used where appropriate (Implementing Regulation annex 11.7 covers multi-factor only; it has no section on secured communications). | — | — | A.5.14, A.8.5 |
| Art. 21(3) | Supplier vulnerabilities and quality when choosing supply chain measures | Evidence that supplier choices take into account each direct supplier's known vulnerabilities, product quality and secure development practice, and any EU-level coordinated supply chain risk assessment. | — | Art. 25 | A.5.19, A.5.21, A.5.22 |
| Art. 21(4) | Corrective measures when the Art. 21(2) measures are not met | Evidence that when a gap against the Art. 21(2) measures is found, corrective action is taken without undue delay and tracked to closure (Implementing Regulation annex 2.3 has corrective actions on review results). | — | — | A.5.35, A.5.36 |
| Art. 23(1) | Notifying the CSIRT or authority of significant incidents | Evidence that the organisation can tell which incidents are significant for it and notifies its CSIRT or competent authority without undue delay, and affected service recipients where appropriate (Implementing Regulation Art. 3 sets criteria for in-scope digital entities). | — | Art. 26, Art. 73 | A.5.5, A.5.24, A.5.25 |
| Art. 23(2) | Informing service recipients of significant cyber threats | Evidence that recipients of the service who may be affected by a significant cyber threat are told what measures or remedies they can apply, and of the threat itself where appropriate. | — | — | A.5.26 |
| Art. 23(4)(a) | Early warning within 24 hours | Evidence of a process to send an early warning within 24 hours of becoming aware of a significant incident, saying whether malicious acts are suspected or cross-border impact is possible. | — | Art. 73 | A.5.5, A.5.26, A.6.8 |
| Art. 23(4)(b) | Incident notification within 72 hours | Evidence of a process to send an incident notification within 72 hours that updates the early warning with an initial assessment of severity and impact and, where known, indicators of compromise. | — | Art. 73 | A.5.5, A.5.25, A.5.26 |
| Art. 23(4)(c) | Intermediate report on request | Evidence that a status-update report on an ongoing significant incident can be produced when the CSIRT or authority asks for one. | — | Art. 73 | A.5.5, A.5.26 |
| Art. 23(4)(d) | Final report within one month | Evidence of a process to deliver a final report within one month of the incident notification (or a progress report then and a final one later if the incident is still ongoing), covering root cause, mitigation and impact. | — | Art. 73 | A.5.5, A.5.27, A.5.28 |

## DORA Regulation (EU) 2022/2554

Key `DORA`. Attestation-led: every row reads Unverified until attested.

| Id | Heading | What we look for | Checks | EU AI Act | ISO/IEC 27001 Annex A |
|---|---|---|---|---|---|
| Art. 5(1)-(2) | Governance and organisation: management body accountability | Evidence that the management body owns, approves and oversees the ICT risk arrangements, including the resilience strategy, budget, continuity plans, internal audit plans and reporting on third-party providers and major incidents. | — | Art. 17 | A.5.1, A.5.2, A.5.4 |
| Art. 5(3) | Governance and organisation: ICT third-party oversight role | Evidence that a named role or senior manager is assigned to monitor ICT third-party arrangements and their documentation (entities other than microenterprises). | — | — | A.5.2, A.5.19 |
| Art. 5(4) | Governance and organisation: management body ICT knowledge | Evidence that members of the management body keep their ICT risk knowledge and skills current through regular training matched to the risk being managed. | — | — | A.6.3 |
| Art. 6(1)-(3) | ICT risk management framework: framework and asset protection | Evidence of a documented ICT risk management framework inside overall risk management, with strategies, policies, protocols and tools protecting information and ICT assets, and complete information available to the supervisor on request. | — | Art. 9, Art. 17 | A.5.1, A.5.2 |
| Art. 6(4) | ICT risk management framework: control function and independence | Evidence that ICT risk oversight sits with a control function kept separate from ICT operations and internal audit, to avoid conflicts of interest (entities other than microenterprises). | — | — | A.5.2, A.5.3 |
| Art. 6(5) | ICT risk management framework: documentation and review | Evidence that the framework is documented, reviewed at least yearly and after major incidents, supervisory instructions or test and audit findings, and improved from lessons learned (periodic review for microenterprises). | — | Art. 9 | A.5.35, A.5.36 |
| Art. 6(6)-(7) | ICT risk management framework: internal audit and follow-up | Evidence of regular internal audit of the ICT risk framework by suitably skilled, independent auditors, and a formal process to verify and fix critical audit findings on time. | — | — | A.5.35 |
| Art. 6(8) | ICT risk management framework: digital operational resilience strategy | Evidence of a written resilience strategy setting ICT risk tolerance, security objectives and metrics, reference architecture, detection and prevention mechanisms, testing plans and an incident communication approach. | — | — | A.5.1 |
| Art. 7 | ICT systems, protocols and tools | Evidence that the ICT systems and tools in use are kept up to date, reliable, sized for peak volumes, including after new technology is introduced, and resilient under stress. | — | Art. 15 | A.8.6, A.8.8 |
| Art. 8 | Identification | Evidence of current inventories of ICT-supported business functions, information and ICT assets and third-party dependencies, with ICT risk sources and scenarios reviewed at least yearly and risk assessed after major changes. | — | Art. 9 | A.5.9, A.5.12, A.8.8 |
| Art. 9 | Protection and prevention | Evidence of continuous monitoring and preventive controls: an information security policy, network segmentation, access restriction, strong authentication and encryption, documented change management and patching. | — | Art. 15 | A.5.1, A.5.14, A.5.15, A.5.18, A.8.2, A.8.3, A.8.5, A.8.8, A.8.20, A.8.22, A.8.24, A.8.32 |
| Art. 10 | Detection | Evidence of mechanisms and resources that promptly spot anomalous activity and incidents, with alert thresholds, automatic alerts to responders, user activity monitoring and regular testing of the detection mechanisms. | event_log_evidence (probe) | Art. 12 | A.8.15, A.8.16 |
| Art. 11 | Response and recovery | Evidence of an ICT business continuity policy with response and recovery plans, a business impact analysis, at least yearly plan testing, a crisis management function and records kept while plans are active. | — | Art. 15 | A.5.26, A.5.29, A.5.30, A.8.14 |
| Art. 12 | Backup policies and procedures, restoration and recovery procedures and methods | Evidence of documented backup and restoration procedures, tested backup systems, segregated restore systems, redundant capacity, recovery time and point objectives, and data integrity checks after recovery. | — | Art. 15 | A.8.13, A.8.14, A.5.30 |
| Art. 13 | Learning and evolving | Evidence of vulnerability and threat intelligence gathering, post-incident reviews, lessons fed back into the framework, yearly reporting to the management body and compulsory ICT security awareness and resilience training. | — | Art. 72 | A.5.7, A.5.27, A.6.3 |
| Art. 14 | Communication | Evidence of crisis communication plans and internal and external communication policies, with a named person handling public and media communication about ICT incidents. | — | — | A.5.24 |
| Art. 16 | Simplified ICT risk management framework | Applies only to the small entities listed in Art. 16(1): evidence of the lighter framework that replaces Arts 5-15, covering monitoring, resilient systems, detection, key third-party dependencies, continuity with backups, regular tests and training. | — | Art. 9, Art. 17 | A.5.19, A.5.30, A.8.13, A.8.16 |
| Art. 17 | ICT-related incident management process | Evidence of a defined process to detect, record, categorise, escalate and respond to ICT incidents and significant cyber threats, with early warning indicators, assigned roles and root causes identified and fixed. | — | Art. 12, Art. 73 | A.5.24, A.5.26, A.5.27, A.5.28, A.6.8 |
| Art. 18 | Classification of ICT-related incidents and cyber threats | Evidence that incidents are classified against the Art. 18 impact criteria (clients and transactions affected, duration, geographic spread, data loss, service criticality, economic impact) and cyber threats are rated for significance. | — | Art. 73 | A.5.25 |
| Art. 19(1), (4) | Reporting of major ICT-related incidents to authorities | Evidence of a route to report major ICT incidents to the competent authority as an initial notification, intermediate reports and a final report, using the prescribed templates and time limits. | — | Art. 73 | A.5.5, A.5.26, A.6.8 |
| Art. 19(3) | Informing clients of major ICT-related incidents | Evidence that clients affected by a major incident are told promptly what happened and what is being done, and clients exposed to a significant cyber threat are told what protective steps they can take. | — | — | A.5.26 |
| Art. 24 | General requirements for digital operational resilience testing | Evidence of a risk-based resilience testing programme run by independent testers, with prioritised remediation of findings and at least yearly tests of systems supporting critical or important functions (entities other than microenterprises). | ai_red_team_report (probe) | Art. 15 | A.5.35, A.8.29 |
| Art. 25 | Testing of ICT tools and systems | Evidence that the testing programme runs suitable tests, such as vulnerability scans, network and source code reviews, scenario, performance and end-to-end tests and penetration tests. | ai_red_team_report (probe) | Art. 15 | A.8.8, A.8.29 |
| Art. 26 | Advanced testing of ICT tools, systems and processes based on TLPT | Only for entities that authorities require to do it: evidence of threat-led penetration testing at least every three years on live critical functions, with provider participation, risk controls and a findings summary sent to the authority. | — | Art. 15 | A.8.29, A.8.34 |
| Art. 27 | Requirements for testers for the carrying out of TLPT | Evidence that TLPT testers meet the suitability, expertise, certification, independent assurance and insurance conditions, that contracts protect test data, and that internal testers have authority approval and external threat intelligence. | — | — | A.5.20, A.6.1 |
| Art. 28(1) | General principles: ICT third-party risk inside the framework | Evidence that ICT third-party risk is managed as part of the ICT risk framework in proportion to the dependency, and that the entity remains fully responsible for its obligations when it relies on ICT services. | — | Art. 25 | A.5.19 |
| Art. 28(2) | General principles: strategy on ICT third-party risk | Evidence of an adopted, regularly reviewed strategy and policy on ICT third-party risk, including for services supporting critical or important functions (not for Art. 16 entities or microenterprises). | — | — | A.5.19 |
| Art. 28(3) | General principles: register of information | Evidence of an up-to-date register of all contracts for ICT services, separating those supporting critical or important functions, that can be reported yearly and given to the supervisor on request. | — | — | A.5.9, A.5.19 |
| Art. 28(4) | General principles: assessment before contracting | Evidence that before signing, the entity checks whether the service supports a critical or important function, whether supervisory conditions are met, assesses risks including concentration, and does due diligence and conflict checks. | — | Art. 25 | A.5.19, A.5.21 |
| Art. 28(5) | General principles: provider information security standards | Evidence that contracts are made only with providers meeting appropriate information security standards, with the most up-to-date and highest quality standards considered for critical or important functions. | — | — | A.5.19, A.5.20 |
| Art. 28(6) | General principles: audit and inspection rights | Evidence that audit and inspection frequency and scope are set in advance on a risk basis against accepted audit standards, with auditors who have the skills for technically complex services. | — | — | A.5.22 |
| Art. 28(7) | General principles: termination rights | Evidence that ICT service contracts can be ended for significant breach, changed circumstances, weak provider risk management or loss of effective supervision. | — | — | A.5.20 |
| Art. 28(8) | General principles: exit strategies | Evidence of documented, tested and periodically reviewed exit plans for ICT services supporting critical or important functions, with alternatives and transition plans that avoid business disruption. | — | — | A.5.20, A.5.23 |
| Art. 29 | Preliminary assessment of ICT concentration risk at entity level | Evidence that concentration risk is assessed before contracting: provider substitutability, repeated use of the same or closely connected providers, subcontracting chains, insolvency law and third-country factors. | — | — | A.5.19, A.5.21 |
| Art. 30(1)-(2) | Key contractual provisions: written contract and core terms | Evidence that each ICT services contract is in writing and covers the core terms: service and sub-contracting description, locations, data protection, data return, service levels, incident help, authority cooperation, termination and training. | — | Art. 25 | A.5.19, A.5.20 |
| Art. 30(3) | Key contractual provisions: critical or important functions | Evidence that contracts for critical or important functions add full service levels, notification duties, continuity and security requirements, TLPT cooperation, access and audit rights, and an exit transition period. | — | Art. 25 | A.5.20, A.5.22, A.5.30 |
| Art. 45 | Information-sharing arrangements on cyber threat information and intelligence | Only if the entity joins a threat-information sharing community (sharing is optional): evidence of participation rules, confidentiality and data-protection safeguards, and notice to the supervisor of joining or leaving. | — | — | A.5.6, A.5.7 |

## EBA Guidelines

Key `EBA`. Attestation-led: every row reads Unverified until attested.

| Id | Heading | What we look for | Checks | EU AI Act | ISO/IEC 27001 Annex A |
|---|---|---|---|---|---|
| GL/2019/04 3.8 | Payment service user relationship management | Only this section (paras 92-98) survives EBA/GL/2025/02, which deleted 3.1-3.7 in favour of DORA Arts 5-16; evidence that payment service providers (credit, e-money and payment institutions) give users security guidance, optional controls (disable functions, adjust limits, alerts) and support. | — | — | — |
| GL/2019/02 Section 3 | Outsourcing (Title II, assessment of arrangements) | Evidence that third-party arrangements are tested against the outsourcing definition (a function performed on a recurrent or ongoing basis), including multi-function arrangements, and that the listed exclusions are applied consistently. | — | — | — |
| GL/2019/02 Section 4 | Critical or important functions | Evidence of a documented method for deciding whether an outsourced function is critical or important (authorisation, financial performance, continuity, core business lines, critical functions) and a record of each outcome. | — | — | — |
| GL/2019/02 Section 5 | Sound governance arrangements and third-party risk | Evidence that risks from all third-party arrangements, outsourcing or not, are identified, assessed and managed in an institution-wide risk and control framework, including GDPR compliance for those arrangements. | — | — | A.5.19, A.5.34 |
| GL/2019/02 Section 6 | Sound governance arrangements and outsourcing | Evidence that the management body stays accountable for outsourced activities, that responsibility and resources for outsourcing are assigned, and that the institution keeps enough substance not to become an empty shell. | — | — | A.5.2, A.5.4 |
| GL/2019/02 Section 7 | Outsourcing policy | Evidence of a written outsourcing policy approved and regularly reviewed by the management body, covering the arrangement life cycle: roles, planning, risk assessment, due diligence, conflicts, continuity, oversight and exit. | — | — | A.5.19 |
| GL/2019/02 Section 8 | Conflicts of interests | Evidence that conflicts of interest created by outsourcing, including with group or scheme entities, are identified, assessed and managed. | — | — | — |
| GL/2019/02 Section 9 | Business continuity plans | Evidence of continuity plans that cover a critical or important outsourced function degrading or failing, including provider insolvency. | — | — | A.5.29, A.5.30 |
| GL/2019/02 Section 10 | Internal audit function | Evidence that internal audit reviews outsourced activities on a risk basis, covers critical or important arrangements in its plan, and checks the outsourcing framework and policy work in practice. | — | — | A.5.35 |
| GL/2019/02 Section 11 | Documentation requirements | Evidence of an up-to-date register of all outsourcing arrangements, with extra fields for critical or important functions, producible for the supervisor on request, plus documented assessments, monitoring results and notices to the supervisor (for ICT services of DORA entities the DORA Art. 28(3) register applies). | — | — | A.5.9 |
| GL/2019/02 Section 12.1 | Supervisory conditions for outsourcing | Evidence that functions needing authorisation (banking activities or payment services) go only to providers that are authorised, registered or otherwise allowed, and that third-country providers meet the supervision and cooperation conditions. | — | — | — |
| GL/2019/02 Section 12.2 | Risk assessment of outsourcing arrangements | Evidence of a pre-outsourcing risk assessment with scenarios, weighing of benefits and costs, and attention to sub-outsourcing, concentration and data sensitivity, repeated during ongoing monitoring. | — | Art. 25 | A.5.19, A.5.21 |
| GL/2019/02 Section 12.3 | Due diligence | Evidence of due diligence showing the provider is suitable, with the reputation, capacity, expertise, controls and data protection measures needed, especially for critical or important functions. | — | Art. 25 | A.5.19 |
| GL/2019/02 Section 13 | Contractual phase | Evidence that outsourcing agreements are in writing and, for critical or important functions, hold the required terms: function description, dates, law, locations, service levels, reporting, continuity, data access, insurance and authority cooperation. | — | Art. 25 | A.5.20 |
| GL/2019/02 Section 13.1 | Sub-outsourcing of critical or important functions | Evidence that the agreement states whether and how critical functions may be sub-outsourced, with conditions, exclusions, flow-down duties and a right to object to material changes. | — | — | A.5.20, A.5.21 |
| GL/2019/02 Section 13.2 | Security of data and systems | Evidence that agreements set data and system security requirements, provider compliance with IT security standards is monitored, and data location and transfer risks, including cloud and third-country processing, are assessed (ICT services of DORA entities: see DORA Art. 30). | — | — | A.5.20, A.5.23 |
| GL/2019/02 Section 13.3 | Access, information and audit rights | Evidence that agreements guarantee access, information and audit rights for the institution, its auditors and authorities, and that audits are planned on a risk basis, with pooled audits or certifications used only where adequate. | — | — | A.5.20, A.5.22 |
| GL/2019/02 Section 13.4 | Termination rights | Evidence that agreements allow termination in defined situations, such as breach, changed circumstances or loss of supervisory access, and support moving the function to another provider or back in-house. | — | — | A.5.20 |
| GL/2019/02 Section 14 | Oversight of outsourced functions | Evidence of ongoing monitoring of provider performance, refreshed risk assessments, reporting to the management body, monitoring of concentration, and corrective action on shortcomings, focused on critical or important functions. | — | — | A.5.22 |
| GL/2019/02 Section 15 | Exit strategies | Evidence of documented exit strategies and plans for critical or important functions covering termination, provider failure and service deterioration, with impact analysis, assigned resources and testing where appropriate. | — | — | A.5.23, A.5.30 |
| GL/2020/06 4.3 | Credit risk policies and procedures | Only the automated-decision parts count here: evidence that credit policies state where automated decision-making is allowed and put governance and model-risk management around automated models (paras 38(g), 41). | — | Art. 6, Art. 9 | — |
| GL/2020/06 4.3.3 | Technology-enabled innovation for credit granting | Evidence that technology-enabled credit tools sit inside the risk framework, are understood by the management body, are traceable and fit for purpose, are checked for data quality and bias, and have output quality monitored with timely remediation. | — | Art. 9, Art. 10, Art. 13, Art. 14, Art. 15 | — |
| GL/2020/06 4.3.4 | Models for creditworthiness assessment and credit decision-making | Evidence that automated creditworthiness and credit decision models are understood and governed: bias and input-quality controls, traceable and robust inputs and outputs, regular output checks with backtesting, overrides and escalation, and model documentation. | — | Art. 6, Art. 10, Art. 11, Art. 12, Art. 14, Art. 15 | — |
| GL/2020/06 4.3.7 | Data infrastructure | Evidence of data infrastructure and procedures that keep exposure, borrower and collateral data continuous, intact and secure over the loan life, granular enough to audit the criteria applied, overrides and policy exceptions. | — | Art. 10, Art. 12 | A.5.33 |
| GL/2020/06 5.1 | Information and documentation | Evidence that data used to judge creditworthiness is sufficient, accurate, current and verified where doubtful, collected within GDPR rules, and that the basis for each approval is documented and kept for the life of the loan. | — | Art. 10 | A.5.33, A.5.34 |

## EIOPA Opinion on AI governance and risk management

Key `EIOPA_AI`. Attestation-led: every row reads Unverified until attested.

| Id | Heading | What we look for | Checks | EU AI Act | ISO/IEC 27001 Annex A |
|---|---|---|---|---|---|
| 3.1-3.6 | Risk-based approach and proportionality | Evidence that each in-scope AI system gets an impact assessment (data scale and sensitivity, customers affected, autonomy, consumer-facing use, prudential effect) and that governance measures are scaled to the result. | — | Art. 9 | — |
| 3.7-3.11 | Risk management system | Evidence of a documented, regularly reviewed approach to AI use across the organisation, covering the whole lifecycle, defined roles and responsibilities, and information and assurances obtained from third-party AI providers. | — | Art. 9, Art. 17, Art. 25 | A.5.1, A.5.2, A.5.19 |
| 3.12-3.16 | Fairness and ethics | Evidence of customer-centric fairness practice for AI systems: ethics guidance and staff training, bias removal in data, regular output monitoring with fairness metrics, and a way for harmed customers to seek redress. | — | Art. 10 | — |
| 3.17-3.21 | Data governance | Evidence of a data governance policy for AI that requires training and test data to be complete, accurate and appropriate, documents data limitations, works to remove bias, and holds externally sourced data to the same standard. | — | Art. 10 | A.5.34 |
| 3.22-3.24 | Documentation and record keeping | Evidence that records of training and testing data and modelling methods are kept well enough to reproduce and trace results, and that higher-risk uses have their records reviewed regularly. | — | Art. 11, Art. 12 | A.5.33, A.5.37 |
| 3.25-3.28 | Transparency and explainability | Evidence that AI outcomes can be meaningfully explained, with explanations suited to authorities, auditors and customers, customers told when they deal with an AI system, and extra safeguards where full explanation is not possible. | — | Art. 13, Art. 50 | — |
| 3.29-3.33 | Human oversight | Evidence of internal controls over the AI lifecycle: defined roles and escalation, management body understanding, compliance, audit, data protection and actuarial involvement, trained staff, and guardrails that catch bias and keep the system within bounds. | — | Art. 4, Art. 14 | A.5.2, A.6.3 |
| 3.34-3.38 | Accuracy, robustness and cybersecurity | Evidence that accuracy, robustness and cybersecurity levels are defined and monitored with suitable metrics, API connections are tested, drift is caught, and the system resists tampering such as data poisoning, with fall-back plans. | — | Art. 15 | A.5.30, A.8.8, A.8.29 |

## GDPR Regulation (EU) 2016/679

Key `GDPR`. Attestation-led: every row reads Unverified until attested.

| Id | Heading | What we look for | Checks | EU AI Act | ISO/IEC 27001 Annex A |
|---|---|---|---|---|---|
| Art. 5 | Principles relating to processing of personal data | Evidence that personal data in the AI system is handled to the core principles: lawful and fair, for stated purposes, no more than needed, accurate, kept no longer than needed, secured, and the organisation can show it. | — | Art. 10 | A.5.34, A.8.10 |
| Art. 6 | Lawfulness of processing | Evidence that each purpose for which the AI system uses personal data, in training and in live use, rests on a documented lawful basis. | — | Art. 10 | A.5.31, A.5.34 |
| Art. 9 | Processing of special categories of personal data | Evidence that sensitive data (health, biometrics, beliefs and the like) is only processed in the AI system under a documented exemption, including any use of such data to detect bias. | — | Art. 10 | A.5.12, A.5.34 |
| Art. 12 | Transparent information and modalities for exercising data subject rights | Evidence that information and replies given to individuals about the AI system's use of their data are in clear plain language, handled in time, and normally free of charge. | — | — | A.5.34 |
| Art. 13 | Information to be provided where data are collected from the data subject | Evidence that people whose data is collected directly are told at that point who is processing it, why, on what basis, with whom it is shared, and what logic applies to any automated decision. | — | Art. 13, Art. 26, Art. 50 | A.5.34 |
| Art. 14 | Information where data have not been obtained from the data subject | Evidence that people whose data reached the AI system from another source (bought, scraped or shared datasets) are informed in good time, or that a documented exception applies. | — | Art. 13, Art. 26, Art. 50 | A.5.34 |
| Art. 15 | Right of access by the data subject | Evidence that the organisation can answer an individual's request for a copy of their data and related processing details, including information on automated decisions, from the AI system's data stores. | — | Art. 13, Art. 26 | A.5.34 |
| Art. 17 | Right to erasure ('right to be forgotten') | Evidence that erasure requests can be carried out across the AI system's data, including training sets, logs and copies passed on, or that a documented ground for refusing applies. | — | — | A.5.34, A.8.10 |
| Art. 21 | Right to object | Evidence that individuals can object to processing based on legitimate or public interest and to profiling or direct marketing, and that objections are acted on unless a compelling reason is documented. | — | — | A.5.34 |
| Art. 22 | Automated individual decision-making, including profiling | Evidence that decisions taken solely by automated means with legal or similarly significant effect have a permitted basis, human intervention and a way to contest; the AI Act's own right to an explanation (its Art. 86) applies only where GDPR does not already give one. | — | Art. 14, Art. 26 | — |
| Art. 24 | Responsibility of the controller | Evidence that the controller has put in place and reviews technical and organisational measures scaled to the AI system's risk, and can show that its processing follows the GDPR. | — | Art. 17, Art. 26 | A.5.1, A.5.2, A.5.34 |
| Art. 25 | Data protection by design and by default | Evidence that privacy protections such as minimisation and pseudonymisation were built into the AI system from the start, and that its defaults expose only the data needed. | — | Art. 10, Art. 15 | A.5.34, A.8.25, A.8.27 |
| Art. 28 | Processor | Evidence that each processor handling personal data for the AI system (model host, labelling or analytics vendor) was vetted and is bound by a written contract with the required terms. | — | Art. 25 | A.5.19, A.5.20, A.5.22 |
| Art. 30 | Records of processing activities | Evidence that a current record of processing exists covering the AI system's purposes, data categories, recipients, transfers, retention periods and security measures. | — | — | A.5.9, A.5.34 |
| Art. 32 | Security of processing | Evidence that security measures suited to the risk protect the AI system's personal data, such as access control, encryption or pseudonymisation, resilience and regular testing. | — | Art. 15 | A.5.15, A.5.34, A.5.35, A.8.11, A.8.13, A.8.24 |
| Art. 33 | Notification of a personal data breach to the supervisory authority | Evidence of a process to detect breaches of the AI system's personal data and report them to the supervisory authority within 72 hours where required, with each breach recorded. | — | Art. 73 | A.5.5, A.5.24, A.5.25, A.5.26, A.5.27, A.5.28, A.6.8 |
| Art. 34 | Communication of a personal data breach to the data subject | Evidence of a process to tell affected individuals, in plain language and without undue delay, when a breach of the AI system's data is likely to put them at high risk, unless a documented exception applies. | — | Art. 73 | A.5.24, A.5.25, A.5.26, A.5.27, A.5.28 |
| Art. 35 | Data protection impact assessment | A DPIA is carried out before processing likely to create a high risk, and its findings feed the AI system's risk work. | — | Art. 26, Art. 27 | A.5.8, A.5.34 |
| Art. 36 | Prior consultation | Evidence that where a DPIA shows a high risk the organisation cannot reduce, the supervisory authority is consulted before the processing starts. | — | — | A.5.5, A.5.34 |
| Art. 37-39 | Designation, position and tasks of the data protection officer | Evidence that a data protection officer is designated where required, is independent and involved early, and carries out the advisory and monitoring tasks for the AI system's processing. | — | — | A.5.2, A.5.34 |
| Chapter V | Transfers of personal data to third countries or international organisations | Evidence that any transfer of the AI system's personal data outside the EEA (hosting, model APIs, remote support access) rests on an adequacy decision, safeguards or a documented derogation. | — | — | A.5.14, A.5.34 |

## Cyber Resilience Act Regulation (EU) 2024/2847

Key `CRA`. Attestation-led: every row reads Unverified until attested.

| Id | Heading | What we look for | Checks | EU AI Act | ISO/IEC 27001 Annex A |
|---|---|---|---|---|---|
| Art. 13(2) | Cybersecurity risk assessment | A cybersecurity risk assessment is carried out and its outcome shapes every phase from planning to maintenance; for a high-risk AI system it can sit inside the AI risk work. Applies from 11 Dec 2027. | ai_threat_model (probe) | Art. 9 | A.8.25, A.8.27 |
| Art. 13(3) | Documented, updated risk assessment | The risk assessment is written down, reflects intended and foreseeable use and the operating environment, states how each Part I requirement applies, and is kept current during the support period. Applies from 11 Dec 2027. | — | Art. 9 | A.8.25 |
| Art. 13(5) | Due diligence on third-party components | Third-party components, open source included, are vetted before integration so they do not weaken the product. Applies from 11 Dec 2027. | — | Art. 25 | A.5.19, A.5.21, A.8.28 |
| Art. 13(6) | Component flaws reported upstream and fixed | A flaw found in an integrated component is reported to whoever maintains it and fixed under the Part II process, with any fix shared back where appropriate. Applies from 11 Dec 2027. | — | — | A.5.21, A.8.8 |
| Art. 13(7) | Systematic cybersecurity documentation | Cybersecurity facts about the product, including known vulnerabilities and input from third parties, are documented in proportion to the risk, and the risk assessment is updated from them. Applies from 11 Dec 2027. | — | — | A.5.37, A.8.8 |
| Art. 13(8) | Support period and vulnerability handling | A support period is set (five years at least, unless the product is expected to be used for less) with its basis recorded, and vulnerabilities are handled throughout it. Applies from 11 Dec 2027. | — | — | A.8.8 |
| Art. 13(9) | Security updates kept available | Each security update issued during the support period stays available for at least 10 years or the rest of the support period, whichever is longer. Applies from 11 Dec 2027. | — | — | — |
| Art. 13(12) | Documentation, assessment, declaration and CE mark | Before the product is sold, the technical documentation exists, a conformity assessment is done, the EU declaration of conformity is drawn up and the CE marking is applied; for a high-risk AI system the AI Act Art. 43 procedure applies (CRA Art. 12(2)). Applies from 11 Dec 2027. | — | Art. 11, Art. 16, Art. 43 | A.5.31 |
| Art. 13(13) | Documentation kept for 10 years | Technical documentation and the declaration of conformity are kept for the authorities for 10 years or the support period, whichever is longer. Applies from 11 Dec 2027. | — | — | A.5.33 |
| Art. 13(14) | Conformity across series production | Procedures keep series-produced units in line with the rules when processes, design or the applied standards change. Applies from 11 Dec 2027. | — | — | A.8.32 |
| Art. 13(15) | Product identification number | Each product carries a type, batch or serial number, or equivalent on its packaging or paperwork, that identifies it. Applies from 11 Dec 2027. | — | — | — |
| Art. 13(16) | Manufacturer contact details on product | The manufacturer's name and contact details appear on the product, packaging or accompanying paperwork, in a language users and authorities understand. Applies from 11 Dec 2027. | — | Art. 16 | — |
| Art. 13(17) | Single point of contact | One easily found contact point lets users reach the manufacturer, including to report vulnerabilities, without being limited to automated tools. Applies from 11 Dec 2027. | — | — | A.6.8 |
| Art. 13(18) | User information and instructions supplied | Clear, legible Annex II information comes with the product and stays available for 10 years or the support period, whichever is longer. Applies from 11 Dec 2027. | — | Art. 13 | — |
| Art. 13(19) | Support period end date stated | The end date of the support period, at least month and year, is stated at purchase, with an end-of-support notice to users where feasible. Applies from 11 Dec 2027. | — | — | — |
| Art. 13(20) | Declaration of conformity supplied | A copy of the EU declaration of conformity, or a simplified one giving the web address of the full text, goes with the product. Applies from 11 Dec 2027. | — | — | — |
| Art. 13(21) | Corrective action, withdrawal or recall | If the product or the manufacturer's processes are found not to conform, corrective action, withdrawal or recall follows immediately. Applies from 11 Dec 2027. | — | — | — |
| Art. 13(22) | Cooperation with market surveillance | On a reasoned request the manufacturer gives a market surveillance authority the documentation it needs and cooperates on risk-removing measures. Applies from 11 Dec 2027. | — | — | A.5.5 |
| Art. 13(23) | Notice before ceasing operations | If the manufacturer is about to stop operating and so cannot meet the Regulation, authorities and, where possible, users are told beforehand. Applies from 11 Dec 2027. | — | — | — |
| Art. 14(1) | Actively exploited vulnerability reporting | Actively exploited vulnerabilities are notified to the lead CSIRT and ENISA through the single reporting platform: early warning in 24 hours, fuller notice in 72 hours, final report within 14 days of a fix being available. Applies from 11 Sep 2026, also to products already on the market. | — | — | A.5.5, A.5.24, A.5.26, A.8.8 |
| Art. 14(3) | Severe incident reporting | Severe incidents affecting product security are notified through the single reporting platform: early warning in 24 hours, notice in 72 hours, final report within one month. Applies from 11 Sep 2026, also to products already on the market. | — | Art. 73 | A.5.5, A.5.24, A.5.25, A.5.26, A.6.8 |
| Art. 14(8) | Users informed of exploited flaws and incidents | Impacted users, and all users where fitting, are told of an exploited vulnerability or severe incident and what they can do, ideally in machine-readable form. Applies from 11 Sep 2026, also to products already on the market. | — | — | A.5.26 |
| Art. 28 | EU declaration of conformity | An EU declaration of conformity in the Annex V structure is drawn up, kept current and available in the required languages; for a high-risk AI system it must also show the AI Act Art. 15 cybersecurity level was achieved (CRA Art. 12(1)(c)). Applies from 11 Dec 2027. | — | Art. 15, Art. 16, Art. 43 | — |
| Art. 30 | CE marking | The CE marking is affixed visibly, legibly and indelibly, or on packaging, declaration or website for software, before the product is placed on the market. Applies from 11 Dec 2027. | — | Art. 16 | — |
| Annex I Part I (1) | Risk-based level of cybersecurity by design | The product's overall security level is set to match the risks it faces and designed in from the start. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.8.25, A.8.26, A.8.27 |
| Annex I Part I (2)(a) | No known exploitable vulnerabilities at release | Nothing ships with a vulnerability already known to be exploitable. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.8.8, A.8.29 |
| Annex I Part I (2)(b) | Secure by default configuration | Out-of-the-box settings are secure, and the user can reset the product to its original state. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.8.9, A.8.27 |
| Annex I Part I (2)(c) | Vulnerabilities fixable by security updates | Security fixes can be delivered as updates, with automatic installation on by default, an easy opt-out and a way to defer. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.8.8, A.8.32 |
| Annex I Part I (2)(d) | Protection from unauthorised access | Authentication and access-management controls block unauthorised access, and suspected unauthorised access is reported. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.5.15, A.5.16, A.8.5 |
| Annex I Part I (2)(e) | Confidentiality of data | Stored, transmitted and processed data stays confidential, for example through current encryption. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.5.14, A.8.24 |
| Annex I Part I (2)(f) | Integrity of data, commands and programs | Data, commands, programs and configuration are protected from unauthorised change, and corruption is reported. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.8.16, A.8.24 |
| Annex I Part I (2)(g) | Data minimisation | The product handles only the data it needs for its stated purpose. Applies from 11 Dec 2027. | — | — | A.5.34, A.8.11 |
| Annex I Part I (2)(h) | Availability of essential functions | Core functions keep working, including after an incident and under denial-of-service attempts. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.8.6, A.8.14 |
| Annex I Part I (2)(i) | Limited impact on other devices and networks | The product limits any harm it can do to the availability of other devices, services or networks. Applies from 11 Dec 2027. | — | — | A.8.20 |
| Annex I Part I (2)(j) | Limited attack surface | Exposed interfaces and other attack surfaces are kept to a minimum by design. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.8.26, A.8.27 |
| Annex I Part I (2)(k) | Exploitation mitigation | Built-in mitigations reduce the damage if an attack on the product succeeds. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.8.27, A.8.28 |
| Annex I Part I (2)(l) | Security logging and monitoring | Relevant internal activity, including access to or change of data, services and functions, is recorded and monitored as security information, with a user opt-out. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 12, Art. 15 | A.8.15, A.8.16 |
| Annex I Part I (2)(m) | Secure permanent data removal | Users can permanently erase all their data and settings, and any data that can move to other systems moves securely. Applies from 11 Dec 2027. | — | — | A.7.14, A.8.10 |
| Annex I Part II (1) | Vulnerabilities and components documented, SBOM | Known vulnerabilities and product components are documented, including a machine-readable software bill of materials covering at least top-level dependencies. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | ai_supply_chain_pins (probe) | Art. 15 | A.5.9, A.5.21, A.8.8 |
| Annex I Part II (2) | Vulnerabilities remediated without delay | Vulnerabilities are fixed promptly in proportion to risk, with security updates shipped apart from feature updates where feasible. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.8.8, A.8.32 |
| Annex I Part II (3) | Regular security tests and reviews | Security tests and reviews of the product are run regularly and are effective. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.8.8, A.8.29 |
| Annex I Part II (4) | Public disclosure of fixed vulnerabilities | After a fix ships, what was fixed, who is affected, how severe it is and how to remediate are published; publication may wait only in justified cases. Applies from 11 Dec 2027. | — | — | A.8.8 |
| Annex I Part II (5) | Coordinated vulnerability disclosure policy | A coordinated vulnerability disclosure policy is in place and enforced. Applies from 11 Dec 2027. | — | — | A.6.8, A.8.8 |
| Annex I Part II (6) | Vulnerability information sharing and contact | Information on potential flaws, including in third-party components, is shared, and a contact address for reports is provided. Applies from 11 Dec 2027. | — | — | A.5.6, A.6.8 |
| Annex I Part II (7) | Secure distribution of updates | Updates reach users through a secure distribution mechanism, automatic for security updates where applicable. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.8.24, A.8.32 |
| Annex I Part II (8) | Updates disseminated without delay | Security updates go out without delay, free of charge unless otherwise agreed for tailor-made products, with advisory messages telling users what to do. Also feeds the CRA Art. 12 presumption that a high-risk AI system meets AI Act Art. 15 cybersecurity. Applies from 11 Dec 2027. | — | Art. 15 | A.8.8 |
| Annex II (1) | Manufacturer identity and contact | The manufacturer's name and contact details come with the product. Applies from 11 Dec 2027. | — | Art. 13 | — |
| Annex II (2) | Vulnerability reporting contact | The user information names a single contact point for vulnerability reports and where the disclosure policy can be found. Applies from 11 Dec 2027. | — | — | — |
| Annex II (3) | Product identification | The user information identifies the exact product by name, type and any other identifying detail. Applies from 11 Dec 2027. | — | — | — |
| Annex II (4) | Intended purpose and security properties | The user information states the intended purpose, the security environment the manufacturer provides, essential functions and security properties. Applies from 11 Dec 2027. | — | Art. 13 | — |
| Annex II (5) | Known risk circumstances and foreseeable misuse | The user information warns of known or foreseeable situations, including reasonably foreseeable misuse, that could create significant cybersecurity risk. Applies from 11 Dec 2027. | — | Art. 13 | — |
| Annex II (6) | Web address of declaration of conformity | Where there is one, the user information gives the web address of the EU declaration of conformity. Applies from 11 Dec 2027. | — | — | — |
| Annex II (7) | Security support offered and end date | The user information states what technical security support is offered and when the support period ends. Applies from 11 Dec 2027. | — | — | — |
| Annex II (8) | Instructions for secure use through to decommissioning | The user information gives instructions, or a link to them, covering secure commissioning and use, effects of changes, installing updates, decommissioning with data removal, turning off automatic updates, and what integrators need. Applies from 11 Dec 2027. | — | Art. 13 | — |
| Annex II (9) | Location of the SBOM if offered | If a software bill of materials is made available to users, the user information says where to find it. Applies from 11 Dec 2027. | — | — | — |
| Annex VII (1) | General description of the product | The technical file describes the product: purpose, software versions that affect conformity, hardware appearance where relevant, and the user information. Applies from 11 Dec 2027. | — | Art. 11 | — |
| Annex VII (2) | Design, development, production, vulnerability handling | The technical file covers design, development, production and vulnerability handling, including architecture, the SBOM, the disclosure policy, the reporting contact and how updates are distributed securely. Applies from 11 Dec 2027. | — | Art. 11 | — |
| Annex VII (3) | Cybersecurity risk assessment in the file | The technical file holds the cybersecurity risk assessment and shows how Part I requirements apply, with a clear justification for any that do not; for a high-risk AI system it can be part of the AI risk work. Applies from 11 Dec 2027. | — | Art. 9, Art. 11 | — |
| Annex VII (4) | Basis for the support period | The technical file records what was considered in setting the support period. Applies from 11 Dec 2027. | — | — | — |
| Annex VII (5) | Standards and solutions applied | The technical file lists the harmonised standards, common specifications or certification schemes applied, in full or part, and describes other solutions used where none were. Applies from 11 Dec 2027. | — | Art. 11 | — |
| Annex VII (6) | Test reports | The technical file contains the test reports showing the product and its vulnerability handling meet Annex I. Applies from 11 Dec 2027. | — | Art. 11, Art. 15 | A.8.29 |
| Annex VII (7) | Copy of the declaration of conformity | The technical file contains a copy of the EU declaration of conformity. Applies from 11 Dec 2027. | — | Art. 11 | — |
| Annex VII (8) | SBOM available on authority request | A software bill of materials can be produced for a market surveillance authority on a reasoned request. Applies from 11 Dec 2027. | — | — | — |

## ETSI EN 304 223

Key `ETSI_EN_304_223`. Attestation-led: every row reads Unverified until attested.

| Id | Heading | What we look for | Checks | EU AI Act | ISO/IEC 27001 Annex A |
|---|---|---|---|---|---|
| 5.1.1-1 | P1 Awareness: AI content in security training | Evidence that the staff training plan contains an AI-threat module, its revision history shows updates as the threat picture shifted, and attendance records exist. Applies to: any organisation. | — | Art. 4 | A.6.3 |
| 5.1.1-1.1 | P1 Awareness: Training matched to each role | Evidence that course material or a role matrix shows which AI security topics each job family receives, for example separate tracks for engineers and support staff. Applies to: any organisation. | — | Art. 4 | A.6.3 |
| 5.1.1-2 | P1 Awareness: Staff stay current on AI threats | Evidence that staff are briefed on new AI vulnerabilities, shown by briefing notes or awareness-campaign records that also pass on known countermeasures. Applies to: any organisation. | — | Art. 4 | A.5.7, A.6.3 |
| 5.1.1-2.1 | P1 Awareness: Threat updates via several channels | Recommended: evidence that AI threat news is distributed by more than one route, such as a mailing list plus an intranet page, shown by sent items or page history. Applies to: any organisation. | — | — | A.6.3 |
| 5.1.1-2.2 | P1 Awareness: Secure AI coding training for developers | Evidence that engineers completed courses or workshops on building AI systems securely, shown by syllabi and completion records. Applies to: any organisation. | — | Art. 4 | A.6.3, A.8.28 |
| 5.1.2-1 | P2 Secure design: Assess need and risk before building | Evidence that a pre-project assessment record states the problem to be solved, lists the AI security exposures and sets out the mitigations chosen, dated before build approval. Applies to: System Operators; Developers. | — | Art. 9 | A.5.8 |
| 5.1.2-1.1 | P2 Secure design: Data owner joins requirements talks | Evidence that meeting notes or a requirements document show the in-house data owner took part when the system's data needs were decided. Applies to: Developers. | — | — | — |
| 5.1.2-2 | P2 Secure design: Withstands attacks and failures | Evidence that design documents and test results show the system was built to tolerate hostile inputs, malformed requests and component failures. Applies to: Developers; System Operators. | — | Art. 15 | A.8.27 |
| 5.1.2-3 | P2 Secure design: Audit trail of models, data and prompts | Evidence that a traceable history exists for each model, dataset and prompt the system uses, covering how it was run and changed through its life. Applies to: Developers. | — | Art. 11, Art. 12 | A.8.15, A.8.32 |
| 5.1.2-4 | P2 Secure design: Risk assessment of external components | Evidence that each third-party component has a recorded security review that looks at AI-specific hazards, produced through the normal supplier-vetting routine. Applies to: Developers; System Operators. | ai_supply_chain_pins (probe) | Art. 25 | A.5.19, A.5.21 |
| 5.1.2-5 | P2 Secure design: Use fits data sensitivity | Evidence that a record links the planned use of the system to the sensitivity classification of its training data and the protections applied to that data. Applies to: Data Custodians. | — | — | A.5.12 |
| 5.1.2-5.1 | P2 Secure design: Staff encouraged to flag AI risks | Recommended: evidence that staff have an easy way to raise AI security worries, such as a reporting channel, with examples of reports received and handled. Applies to: any organisation. | — | — | A.6.8 |
| 5.1.2-6 | P2 Secure design: Least privilege on connected systems | Evidence that an access review lists what the AI system can reach in connected systems, justifies each permission as necessary and carries a risk rating. Applies to: Developers; System Operators. | — | Art. 15 | A.5.15, A.8.2 |
| 5.1.2-7 | P2 Secure design: Due diligence on external providers | Evidence that supplier due-diligence files exist for each outside AI provider, including a check of whether the provider follows this standard. Applies to: Developers; System Operators. | — | Art. 25 | A.5.19, A.5.21 |
| 5.1.3-1 | P3 Threats and risks: Threat modelling and risk management | Evidence that a threat model document for the AI system exists, with review dates, covering attacks on models and data such as poisoning, inversion and membership inference. Applies to: Developers; System Operators. | ai_threat_model (probe) | Art. 9, Art. 15 | A.5.7, A.8.27 |
| 5.1.3-1.1 | P3 Threats and risks: Repeat when settings change | Evidence that threat model revision records tie each update to a new or changed configuration option or setting. Applies to: Developers; System Operators. | ai_threat_model (probe) | Art. 9 | A.8.9, A.8.32 |
| 5.1.3-1.2 | P3 Threats and risks: Risk from surplus model capability | Evidence that a risk entry covers model features the deployment does not use, such as an idle image or audio capability, with the treatment decided. Applies to: Developers. | — | Art. 9 | A.8.27 |
| 5.1.3-1.3 | P3 Threats and risks: Controls chosen against risk tolerance | Evidence that the risk register links each identified risk to a chosen control and notes how cost and risk tolerance influenced the choice. Applies to: System Operators. | — | Art. 9 | — |
| 5.1.3-2 | P3 Threats and risks: Unresolved threats passed down the chain | Evidence that a hand-off record shows threats the developer could not fix were passed to the operator, and the operator's user notice describes them and suggests actions. Applies to: Developers; System Operators; End-users. | — | Art. 13 | — |
| 5.1.3-3 | P3 Threats and risks: Assurance from external risk owners | Recommended: evidence that where another party carries an AI security risk, the operator holds assurance from that party, such as an attestation or audit report. Applies to: System Operators. | — | Art. 25 | A.5.22 |
| 5.1.3-4 | P3 Threats and risks: Ongoing review against risk appetite | Recommended: evidence that infrastructure reviews happen on a schedule tied to the organisation's stated risk appetite, with minutes noting residual AI risk that was accepted. Applies to: Developers; System Operators. | — | Art. 9 | A.8.16 |
| 5.1.4-1 | P4 Human responsibility: Human oversight capability | Recommended: evidence that the system has features for a person to supervise, step in or override it, such as a review queue or stop control, plus upkeep records. Applies to: Developers; System Operators. | — | Art. 14 | — |
| 5.1.4-2 | P4 Human responsibility: Outputs easy for humans to judge | Recommended: evidence that reviewers can judge outputs easily, shown by explanation views, confidence information or interpretability reports. Applies to: Developers. | — | Art. 13, Art. 14 | — |
| 5.1.4-3 | P4 Human responsibility: Technical measures behind oversight | Evidence that verification records exist for the technical controls that make oversight effective, such as override tests, along with their maintenance history. Applies to: Developers; System Operators. | — | Art. 14 | — |
| 5.1.4-4 | P4 Human responsibility: Check data owner's controls were built in | Recommended: evidence that a traceability matrix maps each control the data owner requires to the place it appears in the build. Applies to: Developers. | — | — | A.8.29 |
| 5.1.4-5 | P4 Human responsibility: End-users told of prohibited uses | Recommended: evidence that users are told which activities the system must not be used for, shown by acceptable-use text or onboarding material. Applies to: Developers; System Operators. | — | Art. 13 | — |
| 5.2.1-1 | P5 Assets: Asset inventory with dependencies | Evidence that an asset inventory lists models, datasets, pipelines and services and records how they depend on each other. Applies to: Developers; Data Custodians; System Operators. | ai_supply_chain_pins (probe) | — | A.5.9 |
| 5.2.1-2 | P5 Assets: Track, authenticate and version assets | Evidence that tooling records show AI assets are versioned, verified for authenticity and access-protected, for instance through a registry or signed artefacts. Applies to: Developers; Data Custodians; System Operators. | ai_supply_chain_pins (probe) | — | A.5.9, A.8.9 |
| 5.2.1-3 | P5 Assets: Recovery plans cover AI attacks | Evidence that the disaster recovery plan has scenarios for attacks specific to AI, such as tampered training data or a swapped model, with exercise results. Applies to: System Operators. | — | Art. 15 | A.5.30, A.8.13 |
| 5.2.1-3.1 | P5 Assets: Restorable known-good state | Recommended: evidence that a trusted earlier version of the system can be brought back, shown by a successful restore test. Applies to: System Operators. | — | Art. 15 | A.8.13 |
| 5.2.1-4 | P5 Assets: Protect sensitive training and test data | Evidence that access controls and permission lists cover training and test datasets, with logs showing who touched them. Applies to: Developers; Data Custodians; System Operators; End-users. | — | Art. 15 | A.5.15, A.8.3 |
| 5.2.1-4.1 | P5 Assets: Check and sanitise data and inputs | Evidence that data validation and cleansing records exist for training inputs, and the same steps were rerun when the model was retrained or revised. Applies to: Developers; Data Custodians; System Operators. | — | Art. 10, Art. 15 | — |
| 5.2.1-4.2 | P5 Assets: Protect confidential data and weights | Evidence that a protection scheme, for example encryption or restricted storage, covers confidential datasets and model weight files. Applies to: Developers. | — | Art. 15 | A.8.3, A.8.24 |
| 5.2.2-1 | P6 Infrastructure: Access control for APIs, models and data | Evidence that an access control review covering interfaces, models, datasets and pipelines exists, with the resulting measures documented. Applies to: Developers; System Operators. | — | Art. 15 | A.5.15, A.5.18, A.8.3 |
| 5.2.2-2 | P6 Infrastructure: Controls on externally offered APIs | Evidence that configuration or code shows safeguards on the public model API, such as request quotas, with test results. Applies to: Developers. | — | Art. 15 | A.8.20 |
| 5.2.2-3 | P6 Infrastructure: Separate development and tuning environments | Evidence that architecture diagrams and access settings show build and tuning work happens in separate, tightly permissioned environments. Applies to: Developers. | — | — | A.5.15, A.8.31 |
| 5.2.2-4 | P6 Infrastructure: Published vulnerability disclosure policy | Evidence that a vulnerability disclosure policy is on the public website with a reporting address. Applies to: Developers; System Operators. | — | — | A.6.8, A.8.8 |
| 5.2.2-5 | P6 Infrastructure: Tested incident and recovery plans | Evidence that an AI incident response plan and a recovery plan exist, with records of exercises and updates. Applies to: Developers; System Operators. | — | Art. 15, Art. 73 | A.5.24, A.5.26 |
| 5.2.2-6 | P6 Infrastructure: Cloud contracts back these requirements | Recommended: evidence that cloud provider agreements contain security terms matching these requirements, shown by contract clauses. Applies to: Developers; System Operators. | — | Art. 25 | A.5.20, A.5.23 |
| 5.2.3-1 | P7 Supply chain: Secure software supply-chain process | Evidence that the build and release process for AI components uses controlled sources, integrity checks and dependency tracking, shown by pipeline settings. Applies to: Developers; System Operators. | ai_supply_chain_pins (probe) | Art. 25 | A.5.21 |
| 5.2.3-2 | P7 Supply chain: Justify weakly documented components | Evidence that a written rationale exists for each model or component adopted despite thin documentation or weak security, such as a note that no alternative was available. Applies to: System Operators. | ai_supply_chain_pins (probe) | Art. 25 | A.5.21 |
| 5.2.3-2.1 | P7 Supply chain: Mitigations for such components | Evidence that a risk assessment and compensating controls are on file for each such component. Applies to: Developers; System Operators. | — | Art. 9, Art. 25 | A.5.21 |
| 5.2.3-2.2 | P7 Supply chain: Share the justification with end-users | Evidence that the rationale for using weakly documented components is visible to end-users, for example on a published page. Applies to: System Operators. | — | Art. 13 | — |
| 5.2.3-3 | P7 Supply chain: Re-run evaluations on released models | Evidence that evaluation reports exist from tests rerun on each externally released model before the organisation adopted it. Applies to: Developers; System Operators. | — | Art. 15 | A.8.29 |
| 5.2.3-4 | P7 Supply chain: Advance notice of model updates | Evidence that a notice went to end-users ahead of a model change, with a send date before the change date. Applies to: System Operators. | — | — | A.8.32 |
| 5.2.4-1 | P8 Documentation: Audit trail of design and maintenance | Evidence that design and maintenance documentation exists as a dated record and has been shared with downstream operators or data owners. Applies to: Developers. | — | Art. 11 | A.5.37 |
| 5.2.4-1.1 | P8 Documentation: Security-relevant detail in the record | Recommended: evidence that the documentation records security-relevant facts, for instance where training data came from, intended scope, known limits, guardrails and likely failure modes. Applies to: Developers. | — | Art. 10, Art. 11 | — |
| 5.2.4-1.2 | P8 Documentation: Hashes for released model components | Evidence that a published hash or checksum list accompanies each model file shared with others. Applies to: Developers. | ai_supply_chain_pins (probe) | Art. 15 | A.8.24 |
| 5.2.4-2 | P8 Documentation: Provenance of public training data | Evidence that provenance notes for web-sourced training data describe how it was gathered, where it originated and how the model uses it. Applies to: Developers. | — | Art. 10, Art. 11 | — |
| 5.2.4-2.1 | P8 Documentation: Source and time of collected data | Recommended: evidence that each public data source is logged with at least a locator such as a web address and a collection timestamp. Applies to: Developers. | — | Art. 10 | — |
| 5.2.4-3 | P8 Documentation: Log of prompt and configuration changes | Recommended: evidence that edits to system prompts and other behaviour-changing settings leave a change log, such as version control history. Applies to: Developers. | — | Art. 11 | A.8.9, A.8.32 |
| 5.2.5-1 | P9 Testing: Security assessment before release | Evidence that security assessment reports exist for every model, application and system handed to operators or end-users before release. Applies to: Developers. | ai_red_team_report (probe) | Art. 9, Art. 15 | A.8.29 |
| 5.2.5-2 | P9 Testing: Operator testing before deployment | Evidence that pre-go-live test reports prepared by the operator exist, with signs of developer assistance such as shared test plans. Applies to: System Operators; Developers. | ai_red_team_report (probe) | Art. 15 | A.8.29 |
| 5.2.5-2.1 | P9 Testing: Independent security testers | Recommended: evidence that security testing was done by testers outside the build team who have relevant AI skills, such as a third-party test report. Applies to: System Operators; Developers. | ai_red_team_report (probe) | Art. 15 | A.5.35, A.8.29 |
| 5.2.5-3 | P9 Testing: Share test findings with operators | Recommended: evidence that the developer sent testing and evaluation results on to operators, for example a shared results pack. Applies to: Developers. | — | Art. 13 | — |
| 5.2.5-4 | P9 Testing: Outputs do not expose model or data | Recommended: evidence that probing for extraction of model internals or training records was run against outputs, with results. Applies to: Developers. | ai_red_team_report (probe) | Art. 15 | — |
| 5.2.5-4.1 | P9 Testing: Outputs give no unintended control | Recommended: evidence that tests checked whether crafted inputs or outputs could steer the system beyond its intended behaviour, such as injection test results. Applies to: Developers. | ai_red_team_report (probe) | Art. 15 | — |
| 5.3.1-1 | P10 End-user comms: Tell end-users how data is used | Evidence that a data-use statement shown to users explains where their data goes, who can view it and whether it is used to retrain the model; external developers gave operators the same facts. Applies to: System Operators; Developers. | — | Art. 13 | A.5.34 |
| 5.3.1-2 | P10 End-user comms: Usage and configuration guidance | Evidence that user guides or help content cover operating, connecting and configuring the system; where the developer is a separate company, it supplied operators with what they need. Applies to: System Operators; Developers. | — | Art. 13 | — |
| 5.3.1-2.1 | P10 End-user comms: Guidance on limits and failure modes | Evidence that the user guide has a section on proper use, known limits and how the system can fail. Applies to: System Operators. | — | Art. 13 | — |
| 5.3.1-2.2 | P10 End-user comms: Announce security-relevant updates | Evidence that notices or release notes reach users when security-relevant updates ship, written in plain terms. Applies to: System Operators. | — | — | — |
| 5.3.1-3 | P10 End-user comms: Support users after an incident | Recommended: evidence that a written procedure for assisting users and affected parties after a security incident is built into customer contracts. Applies to: Developers; System Operators. | — | — | A.5.24, A.5.26 |
| 5.4.1-1 | P11 Updates: Security updates and patches delivered | Evidence that release notes and patch records show fixes were issued, operators were alerted and the fixes reached end-users. Applies to: Developers; System Operators. | — | Art. 15 | A.8.8 |
| 5.4.1-1.1 | P11 Updates: Fallbacks when updates are impossible | Evidence that a contingency plan describes the stopgap measures used when no patch can be delivered. Applies to: Developers. | — | Art. 15 | A.8.8 |
| 5.4.1-2 | P11 Updates: Major updates re-tested like new models | Recommended: evidence that a major version change triggered a fresh round of security tests, as a new model would, shown by test reports tied to the release. Applies to: Developers. | ai_red_team_report (probe) | Art. 15, Art. 43 | A.8.29, A.8.32 |
| 5.4.1-3 | P11 Updates: Help operators evaluate model changes | Recommended: evidence that operators can trial model changes early, for example through a beta programme or pinned API versions. Applies to: Developers. | — | — | A.8.32 |
| 5.4.2-1 | P12 Monitoring: Log system and user actions | Evidence that retained logs of system events and user actions exist, with a stated purpose of supporting security checks, investigations and fixes. Applies to: System Operators. | — | Art. 12, Art. 26 | A.8.15 |
| 5.4.2-2 | P12 Monitoring: Analyse logs for anomalies and drift | Recommended: evidence that log reviews or automated alerts look for odd behaviour, intrusions and output drift, with findings recorded. Applies to: System Operators. | — | Art. 26, Art. 72 | A.8.15, A.8.16 |
| 5.4.2-3 | P12 Monitoring: Monitor internal states | Recommended: evidence that internal model or system signals are captured and reviewed where useful for spotting threats, such as telemetry dashboards. Applies to: System Operators; Developers. | — | Art. 72 | A.8.16 |
| 5.4.2-4 | P12 Monitoring: Monitor model performance over time | Recommended: evidence that performance metrics are tracked over time and shifts in them are flagged for security review. Applies to: System Operators; Developers. | — | Art. 15, Art. 72 | A.8.16 |
| 5.5.1-1 | P13 Disposal: Dispose of assets on transfer | Evidence that a disposal record exists for training data or model assets that were transferred or shared, showing data custodians took part. Applies to: Developers; System Operators. | — | — | A.5.14, A.8.10 |
| 5.5.1-2 | P13 Disposal: Delete data and configuration at retirement | Evidence that a deletion record covers the data and configuration details of a retired model or system, with data custodians involved in the sign-off. Applies to: Developers; System Operators. | — | — | A.7.14, A.8.10 |

## ISO/IEC 42005:2025

Key `ISO_IEC_42005`. Attestation-led: every row reads Unverified until attested.

| Id | Heading | What we look for | Checks | EU AI Act | ISO/IEC 27001 Annex A | ISO/IEC 42001 |
|---|---|---|---|---|---|---|
| Clause 5.2 | Documenting the process | The organisation has a written AI system impact assessment process that people can find, follow and keep current. | — | Art. 27 | — | A.5.2, Clause 6.1.4 |
| Clause 5.3 | Integration with other organizational management processes | The impact assessment process is wired into the organisation's existing risk, management-system and governance routines rather than running alone. | — | Art. 9, Art. 27 | — | Clause 6.1.2, Clause 6.1.4 |
| Clause 5.4 | Timing of AI system impact assessment | The organisation has decided at which life-cycle stages, and after which changes, an AI system gets an impact assessment, and follows that rule. | — | Art. 9, Art. 27 | — | Clause 8.4, A.5.2 |
| Clause 5.5 | Scope of the AI system impact assessment | Before each assessment starts, the AI system, its uses and the boundaries of what is being assessed are defined. | — | Art. 27 | — | Clause 6.1.4, A.5.2 |
| Clause 5.6 | Allocating responsibilities | Named roles own carrying out, reviewing and signing off impact assessments, and have the authority to do so. | — | Art. 17 | — | Clause 5.3, A.3.2, A.10.2 |
| Clause 5.7 | Establishing thresholds for sensitive uses, restricted uses and impact scales | The organisation has set its own thresholds for sensitive and restricted uses and a scale for rating impacts, and applies them consistently. | — | Art. 5, Art. 6 | — | Clause 6.1.4, A.5.2 |
| Clause 5.8 | Performing the AI system impact assessment | Impact assessments are actually carried out under the defined process, with the people and information they need. | — | Art. 9, Art. 27 | — | Clause 8.4, A.5.4, A.5.5 |
| Clause 5.9 | Analysing the results of the AI system impact assessment | Assessment findings are analysed and turned into conclusions that decision-makers can act on. | — | Art. 9, Art. 27 | — | Clause 8.4, A.5.2 |
| Clause 5.10 | Recording and reporting | Assessment results are recorded and passed on to the internal and external audiences the organisation has identified. | — | Art. 27 | — | Clause 7.5, A.5.3 |
| Clause 5.11 | Approval process | A defined approval step exists for impact assessments, and the records show who signed off each one. | — | — | — | Clause 5.3, A.5.2 |
| Clause 5.12 | Monitoring and review | Assessments are revisited on a schedule and after relevant changes, and the process itself is reviewed to see whether it works. | — | Art. 26, Art. 27 | — | Clause 8.4, Clause 9.1 |
| Clause 6.2 | Scope of the AI system impact assessment | Each written assessment states which AI system, uses and period it covers. | — | Art. 27 | — | A.5.3 |
| Clause 6.3 | AI system information | Each written assessment describes the AI system: what it does, its purpose, and its intended and unintended uses. | — | Art. 11, Art. 27 | — | A.5.3, A.6.2.7, A.9.4 |
| Clause 6.4 | Data information and quality | Each written assessment records what data the system relies on and holds evidence about the quality of that data. | — | Art. 10 | — | A.4.3, A.7.4, A.7.5 |
| Clause 6.5 | Algorithm and model information | Each written assessment records the algorithms and models in use and how they were developed. | — | Art. 11 | — | A.6.2.3, A.6.2.7 |
| Clause 6.6 | Deployment environment | Each written assessment records where and under what conditions the system is deployed, including regions, languages and constraints. | — | Art. 9, Art. 27 | — | A.6.2.5 |
| Clause 6.7 | Relevant interested parties | Each written assessment identifies who is directly affected by the system and which other parties have a stake in it. | — | Art. 27 | — | Clause 4.2, A.5.4 |
| Clause 6.8.2 | Benefits and harms | Each written assessment records the benefits and harms the system can reasonably be expected to bring to individuals, groups and society. | — | Art. 9, Art. 27 | — | Clause 6.1.4, A.5.4, A.5.5 |
| Clause 6.8.3 | AI system failures and reasonably foreseeable misuse | Each written assessment considers what follows when the system fails and when it is misused in ways that could be expected. | — | Art. 9, Art. 27 | — | Clause 6.1.2, A.5.4, A.5.5 |
| Clause 6.9 | Measures to address harms and benefits | Each written assessment lists the measures chosen to reduce harms and preserve benefits, and the organisation tracks them through. | — | Art. 9, Art. 27 | — | Clause 6.1.3, Clause 8.3 |

## ISO/IEC 23894:2023

Key `ISO_IEC_23894`. Attestation-led: every row reads Unverified until attested.

| Id | Heading | What we look for | Checks | EU AI Act | ISO/IEC 27001 Annex A | ISO/IEC 42001 |
|---|---|---|---|---|---|---|
| Clause 4 | Principles of AI risk management | The organisation has adopted the standard's AI risk management principles and can show them applied in how it handles AI risk. | — | Art. 9 | — | Clause 6.1.1, Clause 6.1.2 |
| Clause 5.2 | Leadership and commitment | Top management visibly backs AI risk management and there is evidence of that support. | — | Art. 17 | — | Clause 5.1, Clause 5.2 |
| Clause 5.3 | Integration | AI risk management is built into how the organisation is governed and runs its activities rather than bolted on. | — | Art. 9, Art. 17 | — | Clause 4.4, Clause 6.1.1, Clause 8.1 |
| Clause 5.4.1 | Understanding the organization and its context | The organisation has examined its internal and external context as it bears on managing AI risk. | — | — | — | Clause 4.1, Clause 4.2 |
| Clause 5.4.2 | Articulating risk management commitment | Management has stated, in a form people can read, its commitment to managing AI risk. | — | Art. 17 | — | Clause 5.2, A.2.2 |
| Clause 5.4.3 | Assigning organizational roles, authorities, responsibilities & accountabilities | Roles, authority and accountability for AI risk management are assigned to named people or functions. | — | Art. 17 | — | Clause 5.3, A.3.2 |
| Clause 5.4.4 | Allocating resources | Resources set aside for AI risk management are identified and the allocation is on record. | — | Art. 17 | — | Clause 7.1, A.4.2 |
| Clause 5.4.5 | Establishing communication and consultation | Channels for communicating and consulting with internal and external parties about AI risk are set up. | — | — | — | Clause 7.4, A.8.5 |
| Clause 5.5 | Implementation | The AI risk management framework has been put into operation under a plan, not only designed. | — | Art. 9, Art. 17 | — | Clause 8.1 |
| Clause 5.6 | Evaluation | The organisation checks how well its AI risk management framework is working against its purpose and keeps the results. | — | Art. 17 | — | Clause 9.1, Clause 9.3 |
| Clause 5.7.1 | Adapting | The framework is adjusted when internal or external conditions change, with a record of what was changed. | — | Art. 9 | — | Clause 6.3, Clause 10.1 |
| Clause 5.7.2 | Continually improving | The suitability and effectiveness of the framework are improved over time, with evidence of the improvements. | — | Art. 9 | — | Clause 10.1, Clause 10.2 |
| Clause 6.2 | Communication and consultation | Relevant parties are communicated with and consulted during the risk process, and the exchanges are recorded. | — | — | — | Clause 7.4, A.8.5 |
| Clause 6.3.2 | Defining the scope | The scope of each AI risk management exercise is defined before work starts. | — | Art. 9 | — | Clause 6.1.2 |
| Clause 6.3.3 | External and internal context | The external and internal context around the AI system is understood and written down before risks are assessed. | — | Art. 9 | — | Clause 4.1, Clause 4.2 |
| Clause 6.3.4 | Defining risk criteria | Criteria for judging how significant an AI risk is are defined, and approved, before risks are assessed. | — | Art. 9 | — | Clause 6.1.2 |
| Clause 6.4.2 | Risk identification | AI-related risks, with their sources and possible consequences, are identified and listed. | — | Art. 9 | — | Clause 6.1.2, Clause 8.2 |
| Clause 6.4.3 | Risk analysis | Identified AI risks are analysed to understand their nature, likelihood and level. | — | Art. 9 | — | Clause 6.1.2, Clause 8.2 |
| Clause 6.4.4 | Risk evaluation | Analysed risks are compared against the agreed criteria to decide which ones need treatment. | — | Art. 9 | — | Clause 6.1.2, Clause 8.2 |
| Clause 6.5.2 | Selection of risk treatment options | Treatment options are chosen for risks that need action, with the reasons for the choice recorded. | — | Art. 9 | — | Clause 6.1.3, Clause 8.3 |
| Clause 6.5.3 | Preparing and implementing risk treatment plans | Risk treatment plans exist, are carried out, and the risk left over is understood. | — | Art. 9 | — | Clause 6.1.3, Clause 8.3 |
| Clause 6.6 | Monitoring and review | Risks and the risk process are monitored and reviewed regularly, and the findings are fed back into the work. | — | Art. 9, Art. 72 | — | Clause 9.1, A.6.2.6 |
| Clause 6.7 | Recording and reporting | The risk process and its outcomes are recorded and reported through suitable channels. | — | Art. 11, Art. 17 | — | Clause 7.5 |
