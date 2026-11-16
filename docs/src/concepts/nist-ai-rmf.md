# NIST AI RMF

`NIST_AI_RMF` is the AI Risk Management Framework 1.0 (NIST AI 100-1) as a pack in
Opencomplai. It is a **hybrid** target: most verdicts are re-projected from evidence
Opencomplai already gathers for the EU AI Act, and where that evidence holds nothing for a
subcategory, the provider's attestation stands in. The pack's status is `evaluated`, set by
the parity check (`tools/packs/parity_check.py`), not typed by hand. The framework is
voluntary and nothing here is a certification.

## What it is

The pack holds the 72 subcategories of the RMF 1.0 core (Govern, Map, Measure, Manage). The
outcome text is NIST's, which is public domain. Each row lists the EU AI Act articles whose
evidence covers it, with a mapping confidence of `low` or `medium` (nothing claims `high`),
and the related ISO/IEC 42001 and ISO/IEC 27090 rows. No new scanner was added: nothing
inspects your system, code or model any differently for NIST AI RMF than for the EU AI Act.

## Does it apply to you

Nothing in law requires it, so the pack is voluntary and never changes an EU AI Act row.
Scope answers under `framework_inputs.NIST_AI_RMF.scope` take rows out of the report with a
reason that names the answer, and a row you exclude yourself under `excluded` keeps your
reason. An excluded row never fails a gate.

## How rows are decided

Each row has an evidence class. Of the 72 rows, 54 are `machine`, 2 are `hybrid` and 16 are
`organisational`. **56 of 72 requirements are checked from evidence** (target 40); the other
16 are decided by attestation alone. A row checked from evidence is still a re-projection of
a mapped EU AI Act result, so its verdict is a draft estimate at `low` or `medium` mapping
confidence. Every row reads `mapping not yet reviewed`: no review flag has been cleared.

## Requirements

One row per subcategory, generated from `requirements.json` by
`uv run python tools/packs/pack_doc.py NIST_AI_RMF`.

<!-- rows:start -->
| Requirement | Title | Evidence class | Sources | TTL days | Review |
| --- | --- | --- | --- | --- | --- |
| NIST_AI_RMF:GOVERN 1.1 | Legal and regulatory requirements involving AI are understood, managed, and documented. | machine | crosswalk: NIST_AI_RMF:GOVERN 1.1 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 1.2 | The characteristics of trustworthy AI are integrated into organizational policies, processes, procedures, and practices. | machine | crosswalk: NIST_AI_RMF:GOVERN 1.2; attestation: NIST_AI_RMF:GOVERN 1.2; artifact: policy_ai (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 1.3 | Processes, procedures, and practices are in place to determine the needed level of risk management activities based on the organization's risk tolerance. | machine | crosswalk: NIST_AI_RMF:GOVERN 1.3; attestation: NIST_AI_RMF:GOVERN 1.3; artifact: risk_register (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 1.4 | The risk management process and its outcomes are established through transparent policies, procedures, and other controls based on organizational risk priorities. | machine | crosswalk: NIST_AI_RMF:GOVERN 1.4; attestation: NIST_AI_RMF:GOVERN 1.4; artifact: nist_ai_rmf.profile#govern (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 1.5 | Ongoing monitoring and periodic review of the risk management process and its outcomes are planned and organizational roles and responsibilities clearly defined, including determining the frequency of periodic review. | machine | crosswalk: NIST_AI_RMF:GOVERN 1.5; attestation: NIST_AI_RMF:GOVERN 1.5; artifact: management_review_minutes (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 1.6 | Mechanisms are in place to inventory AI systems and are resourced according to organizational risk priorities. | organisational | crosswalk: NIST_AI_RMF:GOVERN 1.6; attestation: NIST_AI_RMF:GOVERN 1.6 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 1.7 | Processes and procedures are in place for decommissioning and phasing out AI systems safely and in a manner that does not increase risks or decrease the organization's trustworthiness. | organisational | crosswalk: NIST_AI_RMF:GOVERN 1.7; attestation: NIST_AI_RMF:GOVERN 1.7 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 2.1 | Roles and responsibilities and lines of communication related to mapping, measuring, and managing AI risks are documented and are clear to individuals and teams throughout the organization. | machine | crosswalk: NIST_AI_RMF:GOVERN 2.1; attestation: NIST_AI_RMF:GOVERN 2.1 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 2.2 | The organization's personnel and partners receive AI risk management training to enable them to perform their duties and responsibilities consistent with related policies, procedures, and agreements. | machine | crosswalk: NIST_AI_RMF:GOVERN 2.2; attestation: NIST_AI_RMF:GOVERN 2.2; artifact: competence_training_record (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 2.3 | Executive leadership of the organization takes responsibility for decisions about risks associated with AI system development and deployment. | machine | crosswalk: NIST_AI_RMF:GOVERN 2.3; attestation: NIST_AI_RMF:GOVERN 2.3 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 3.1 | Decision-making related to mapping, measuring, and managing AI risks throughout the lifecycle is informed by a diverse team (e.g., diversity of demographics, disciplines, experience, expertise, and backgrounds). | organisational | crosswalk: NIST_AI_RMF:GOVERN 3.1; attestation: NIST_AI_RMF:GOVERN 3.1 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 3.2 | Policies and procedures are in place to define and differentiate roles and responsibilities for human-AI configurations and oversight of AI systems. | machine | crosswalk: NIST_AI_RMF:GOVERN 3.2; artifact: human_oversight_construct | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 4.1 | Organizational policies and practices are in place to foster a critical thinking and safety-first mindset in the design, development, deployment, and uses of AI systems to minimize potential negative impacts. | organisational | crosswalk: NIST_AI_RMF:GOVERN 4.1; attestation: NIST_AI_RMF:GOVERN 4.1 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 4.2 | Organizational teams document the risks and potential impacts of the AI technology they design, develop, deploy, evaluate, and use, and they communicate about the impacts more broadly. | machine | crosswalk: NIST_AI_RMF:GOVERN 4.2; artifact: ai_impact_assessment#impacts (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 4.3 | Organizational practices are in place to enable AI testing, identification of incidents, and information sharing. | machine | crosswalk: NIST_AI_RMF:GOVERN 4.3; attestation: NIST_AI_RMF:GOVERN 4.3; artifact: serious_incident_log (supporting) | 90 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 5.1 | Organizational policies and practices are in place to collect, consider, prioritize, and integrate feedback from those external to the team that developed or deployed the AI system regarding the potential individual and societal impacts related to AI risks. | machine | crosswalk: NIST_AI_RMF:GOVERN 5.1; attestation: NIST_AI_RMF:GOVERN 5.1 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 5.2 | Mechanisms are established to enable the team that developed or deployed AI systems to regularly incorporate adjudicated feedback from relevant AI actors into system design and implementation. | machine | crosswalk: NIST_AI_RMF:GOVERN 5.2; attestation: NIST_AI_RMF:GOVERN 5.2 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 6.1 | Policies and procedures are in place that address AI risks associated with third-party entities, including risks of infringement of a third-party's intellectual property or other rights. | machine | crosswalk: NIST_AI_RMF:GOVERN 6.1; artifact: policy_supplier (supporting); artifact: vendor_register (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:GOVERN 6.2 | Contingency processes are in place to handle failures or incidents in third-party data or AI systems deemed to be high-risk. | machine | crosswalk: NIST_AI_RMF:GOVERN 6.2; artifact: exit_plan (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 1.1 | Intended purposes, potentially beneficial uses, context-specific laws, norms and expectations, and prospective settings in which the AI system will be deployed are understood and documented. Considerations include: the specific set or types of users along with their expectations; potential positive and negative impacts of system uses to individuals, communities, organizations, society, and the planet; assumptions and related limitations about AI system purposes, uses, and risks across the development or product AI lifecycle; and related TEVV and system metrics. | machine | crosswalk: NIST_AI_RMF:MAP 1.1; artifact: ai_impact_assessment#purpose (supporting) | 730 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 1.2 | Interdisciplinary AI actors, competencies, skills, and capacities for establishing context reflect demographic diversity and broad domain and user experience expertise, and their participation is documented. Opportunities for interdisciplinary collaboration are prioritized. | organisational | crosswalk: NIST_AI_RMF:MAP 1.2; attestation: NIST_AI_RMF:MAP 1.2 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 1.3 | The organization's mission and relevant goals for AI technology are understood and documented. | organisational | crosswalk: NIST_AI_RMF:MAP 1.3; attestation: NIST_AI_RMF:MAP 1.3 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 1.4 | The business value or context of business use has been clearly defined or – in the case of assessing existing AI systems – re-evaluated. | organisational | crosswalk: NIST_AI_RMF:MAP 1.4; attestation: NIST_AI_RMF:MAP 1.4 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 1.5 | Organizational risk tolerances are determined and documented. | machine | crosswalk: NIST_AI_RMF:MAP 1.5; attestation: NIST_AI_RMF:MAP 1.5; artifact: risk_register (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 1.6 | System requirements (e.g., “the system shall respect the privacy of its users”) are elicited from and understood by relevant AI actors. Design decisions take socio-technical implications into account to address AI risks. | machine | crosswalk: NIST_AI_RMF:MAP 1.6; attestation: NIST_AI_RMF:MAP 1.6; artifact: technical_documentation_dossier (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 2.1 | The specific tasks and methods used to implement the tasks that the AI system will support are defined (e.g., classifiers, generative models, recommenders). | machine | crosswalk: NIST_AI_RMF:MAP 2.1; attestation: NIST_AI_RMF:MAP 2.1; artifact: model_card (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 2.2 | Information about the AI system’s knowledge limits and how system output may be utilized and overseen by humans is documented. Documentation provides sufficient information to assist relevant AI actors when making decisions and taking subsequent actions. | machine | crosswalk: NIST_AI_RMF:MAP 2.2; artifact: model_card (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 2.3 | Scientific integrity and TEVV considerations are identified and documented, including those related to experimental design, data collection and selection (e.g., availability, representativeness, suitability), system trustworthiness, and construct validation. | machine | crosswalk: NIST_AI_RMF:MAP 2.3; attestation: NIST_AI_RMF:MAP 2.3; artifact: evaluation_evidence (supporting) | 180 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 3.1 | Potential benefits of intended AI system functionality and performance are examined and documented. | organisational | crosswalk: NIST_AI_RMF:MAP 3.1; attestation: NIST_AI_RMF:MAP 3.1 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 3.2 | Potential costs, including non-monetary costs, which result from expected or realized AI errors or system functionality and trustworthiness – as connected to organizational risk tolerance – are examined and documented. | machine | crosswalk: NIST_AI_RMF:MAP 3.2; attestation: NIST_AI_RMF:MAP 3.2; artifact: ai_impact_assessment#impacts (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 3.3 | Targeted application scope is specified and documented based on the system's capability, established context, and AI system categorization. | machine | crosswalk: NIST_AI_RMF:MAP 3.3; artifact: deployer_instructions (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 3.4 | Processes for operator and practitioner proficiency with AI system performance and trustworthiness – and relevant technical standards and certifications – are defined, assessed, and documented. | machine | crosswalk: NIST_AI_RMF:MAP 3.4; attestation: NIST_AI_RMF:MAP 3.4 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 3.5 | Processes for human oversight are defined, assessed, and documented in accordance with organizational policies from the GOVERN function. | machine | crosswalk: NIST_AI_RMF:MAP 3.5; artifact: human_oversight_construct (corroborating) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 4.1 | Approaches for mapping AI technology and legal risks of its components – including the use of third-party data or software – are in place, followed, and documented, as are risks of infringement of a third party’s intellectual property or other rights. | machine | crosswalk: NIST_AI_RMF:MAP 4.1; artifact: vendor_register (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 4.2 | Internal risk controls for components of the AI system, including third-party AI technologies, are identified and documented. | machine | crosswalk: NIST_AI_RMF:MAP 4.2; artifact: ai_supply_chain_pins (supporting) | 90 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 5.1 | Likelihood and magnitude of each identified impact (both potentially beneficial and harmful) based on expected use, past uses of AI systems in similar contexts, public incident reports, feedback from those external to the team that developed or deployed the AI system, or other data are identified and documented. | machine | crosswalk: NIST_AI_RMF:MAP 5.1; attestation: NIST_AI_RMF:MAP 5.1; artifact: ai_impact_assessment#impacts (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MAP 5.2 | Practices and personnel for supporting regular engagement with relevant AI actors and integrating feedback about positive, negative, and unanticipated impacts are in place and documented. | machine | crosswalk: NIST_AI_RMF:MAP 5.2; attestation: NIST_AI_RMF:MAP 5.2; artifact: ai_impact_assessment#affected parties (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 1.1 | Approaches and metrics for measurement of AI risks enumerated during the MAP function are selected for implementation starting with the most significant AI risks. The risks or trustworthiness characteristics that will not – or cannot – be measured are properly documented. | machine | crosswalk: NIST_AI_RMF:MEASURE 1.1; artifact: evaluation_evidence (supporting) | 180 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 1.2 | Appropriateness of AI metrics and effectiveness of existing controls are regularly assessed and updated, including reports of errors and potential impacts on affected communities. | machine | crosswalk: NIST_AI_RMF:MEASURE 1.2; attestation: NIST_AI_RMF:MEASURE 1.2 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 1.3 | Internal experts who did not serve as front-line developers for the system and/or independent assessors are involved in regular assessments and updates. Domain experts, users, AI actors external to the team that developed or deployed the AI system, and affected communities are consulted in support of assessments as necessary per organizational risk tolerance. | organisational | crosswalk: NIST_AI_RMF:MEASURE 1.3; attestation: NIST_AI_RMF:MEASURE 1.3 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.1 | Test sets, metrics, and details about the tools used during TEVV are documented. | machine | crosswalk: NIST_AI_RMF:MEASURE 2.1; attestation: NIST_AI_RMF:MEASURE 2.1; artifact: evaluation_evidence (supporting) | 180 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.2 | Evaluations involving human subjects meet applicable requirements (including human subject protection) and are representative of the relevant population. | organisational | crosswalk: NIST_AI_RMF:MEASURE 2.2; attestation: NIST_AI_RMF:MEASURE 2.2 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.3 | AI system performance or assurance criteria are measured qualitatively or quantitatively and demonstrated for conditions similar to deployment setting(s). Measures are documented. | machine | crosswalk: NIST_AI_RMF:MEASURE 2.3; evaluator: EVAL_CALIBRATION_V1 | 90 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.4 | The functionality and behavior of the AI system and its components – as identified in the MAP function – are monitored when in production. | machine | artifact: post_market_monitoring_plan; crosswalk: NIST_AI_RMF:MEASURE 2.4 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.5 | The AI system to be deployed is demonstrated to be valid and reliable. Limitations of the generalizability beyond the conditions under which the technology was developed are documented. | machine | crosswalk: NIST_AI_RMF:MEASURE 2.5; artifact: evaluation_evidence (supporting) | 180 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.6 | The AI system is evaluated regularly for safety risks – as identified in the MAP function. The AI system to be deployed is demonstrated to be safe, its residual negative risk does not exceed the risk tolerance, and it can fail safely, particularly if made to operate beyond its knowledge limits. Safety metrics reflect system reliability and robustness, real-time monitoring, and response times for AI system failures. | machine | crosswalk: NIST_AI_RMF:MEASURE 2.6; evaluator: EVAL_SAFETY_LEXICAL_V1 | 90 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.7 | AI system security and resilience – as identified in the MAP function – are evaluated and documented. | machine | crosswalk: NIST_AI_RMF:MEASURE 2.7; evaluator: EVAL_ADVERSARIAL_V1; artifact: ai_red_team_report (supporting) | 90 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.8 | Risks associated with transparency and accountability – as identified in the MAP function – are examined and documented. | machine | crosswalk: NIST_AI_RMF:MEASURE 2.8; artifact: model_card (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.9 | The AI model is explained, validated, and documented, and AI system output is interpreted within its context – as identified in the MAP function – to inform responsible use and governance. | machine | crosswalk: NIST_AI_RMF:MEASURE 2.9; artifact: model_card (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.10 | Privacy risk of the AI system – as identified in the MAP function – is examined and documented. | machine | crosswalk: NIST_AI_RMF:MEASURE 2.10; attestation: NIST_AI_RMF:MEASURE 2.10; evaluator: EVAL_DATA_LEAKAGE_V1 (corroborating); artifact: dpia_document (supporting) | 90 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.11 | Fairness and bias – as identified in the MAP function – are evaluated and results are documented. | machine | crosswalk: NIST_AI_RMF:MEASURE 2.11; attestation: NIST_AI_RMF:MEASURE 2.11; evaluator: EVAL_BIAS_FAIRNESS_V1 (corroborating) | 90 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.12 | Environmental impact and sustainability of AI model training and management activities – as identified in the MAP function – are assessed and documented. | organisational | crosswalk: NIST_AI_RMF:MEASURE 2.12; attestation: NIST_AI_RMF:MEASURE 2.12 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 2.13 | Effectiveness of the employed TEVV metrics and processes in the MEASURE function are evaluated and documented. | organisational | crosswalk: NIST_AI_RMF:MEASURE 2.13; attestation: NIST_AI_RMF:MEASURE 2.13 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 3.1 | Approaches, personnel, and documentation are in place to regularly identify and track existing, unanticipated, and emergent AI risks based on factors such as intended and actual performance in deployed contexts. | machine | crosswalk: NIST_AI_RMF:MEASURE 3.1; artifact: risk_register (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 3.2 | Risk tracking approaches are considered for settings where AI risks are difficult to assess using currently available measurement techniques or where metrics are not yet available. | organisational | crosswalk: NIST_AI_RMF:MEASURE 3.2; attestation: NIST_AI_RMF:MEASURE 3.2 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 3.3 | Feedback processes for end users and impacted communities to report problems and appeal system outcomes are established and integrated into AI system evaluation metrics. | organisational | crosswalk: NIST_AI_RMF:MEASURE 3.3; attestation: NIST_AI_RMF:MEASURE 3.3 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 4.1 | Measurement approaches for identifying AI risks are connected to deployment context(s) and informed through consultation with domain experts and other end users. Approaches are documented. | organisational | crosswalk: NIST_AI_RMF:MEASURE 4.1; attestation: NIST_AI_RMF:MEASURE 4.1 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 4.2 | Measurement results regarding AI system trustworthiness in deployment context(s) and across the AI lifecycle are informed by input from domain experts and relevant AI actors to validate whether the system is performing consistently as intended. Results are documented. | hybrid | crosswalk: NIST_AI_RMF:MEASURE 4.2; attestation: NIST_AI_RMF:MEASURE 4.2; artifact: evaluation_evidence (supporting) | 180 | mapping not yet reviewed |
| NIST_AI_RMF:MEASURE 4.3 | Measurable performance improvements or declines based on consultations with relevant AI actors, including affected communities, and field data about context-relevant risks and trustworthiness characteristics are identified and documented. | machine | crosswalk: NIST_AI_RMF:MEASURE 4.3; attestation: NIST_AI_RMF:MEASURE 4.3 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 1.1 | A determination is made as to whether the AI system achieves its intended purposes and stated objectives and whether its development or deployment should proceed. | machine | crosswalk: NIST_AI_RMF:MANAGE 1.1; attestation: NIST_AI_RMF:MANAGE 1.1 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 1.2 | Treatment of documented AI risks is prioritized based on impact, likelihood, and available resources or methods. | machine | crosswalk: NIST_AI_RMF:MANAGE 1.2; attestation: NIST_AI_RMF:MANAGE 1.2; artifact: risk_register (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 1.3 | Responses to the AI risks deemed high priority, as identified by the MAP function, are developed, planned, and documented. Risk response options can include mitigating, transferring, avoiding, or accepting. | machine | crosswalk: NIST_AI_RMF:MANAGE 1.3; attestation: NIST_AI_RMF:MANAGE 1.3; artifact: risk_register (corroborating) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 1.4 | Negative residual risks (defined as the sum of all unmitigated risks) to both downstream acquirers of AI systems and end users are documented. | machine | crosswalk: NIST_AI_RMF:MANAGE 1.4; artifact: risk_register (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 2.1 | Resources required to manage AI risks are taken into account – along with viable non-AI alternative systems, approaches, or methods – to reduce the magnitude or likelihood of potential impacts. | organisational | crosswalk: NIST_AI_RMF:MANAGE 2.1; attestation: NIST_AI_RMF:MANAGE 2.1 | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 2.2 | Mechanisms are in place and applied to sustain the value of deployed AI systems. | machine | crosswalk: NIST_AI_RMF:MANAGE 2.2; attestation: NIST_AI_RMF:MANAGE 2.2; artifact: post_market_monitoring_plan (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 2.3 | Procedures are followed to respond to and recover from a previously unknown risk when it is identified. | machine | crosswalk: NIST_AI_RMF:MANAGE 2.3; attestation: NIST_AI_RMF:MANAGE 2.3; artifact: incident_response_plan (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 2.4 | Mechanisms are in place and applied, and responsibilities are assigned and understood, to supersede, disengage, or deactivate AI systems that demonstrate performance or outcomes inconsistent with intended use. | machine | crosswalk: NIST_AI_RMF:MANAGE 2.4; artifact: human_oversight_construct | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 3.1 | AI risks and benefits from third-party resources are regularly monitored, and risk controls are applied and documented. | machine | crosswalk: NIST_AI_RMF:MANAGE 3.1; artifact: vendor_register (supporting) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 3.2 | Pre-trained models which are used for development are monitored as part of AI system regular monitoring and maintenance. | hybrid | crosswalk: NIST_AI_RMF:MANAGE 3.2; attestation: NIST_AI_RMF:MANAGE 3.2; artifact: ai_supply_chain_pins (supporting) | 90 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 4.1 | Post-deployment AI system monitoring plans are implemented, including mechanisms for capturing and evaluating input from users and other relevant AI actors, appeal and override, decommissioning, incident response, recovery, and change management. | machine | crosswalk: NIST_AI_RMF:MANAGE 4.1; attestation: NIST_AI_RMF:MANAGE 4.1; artifact: post_market_monitoring_plan (corroborating) | 365 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 4.2 | Measurable activities for continual improvements are integrated into AI system updates and include regular engagement with interested parties, including relevant AI actors. | machine | crosswalk: NIST_AI_RMF:MANAGE 4.2; attestation: NIST_AI_RMF:MANAGE 4.2; artifact: corrective_action_log (supporting) | 90 | mapping not yet reviewed |
| NIST_AI_RMF:MANAGE 4.3 | Incidents and errors are communicated to relevant AI actors, including affected communities. Processes for tracking, responding to, and recovering from incidents and errors are followed and documented. | machine | crosswalk: NIST_AI_RMF:MANAGE 4.3; attestation: NIST_AI_RMF:MANAGE 4.3; artifact: serious_incident_log (corroborating); artifact: incident_notification_template (corroborating) | 90 | mapping not yet reviewed |
<!-- rows:end -->

## Scaffolds

`opencomplai scaffold` writes one document for this pack: `AI_RMF_PROFILE.md`, an AI RMF
profile. Its sections hold `_fill in_` text until you replace it, and an unfilled scaffold is
not evidence: the probe `nist_ai_rmf.profile` counts the file only once the placeholders are
gone.

## Timeline (none)

This pack has no timeline: a voluntary framework without legal dates.

## Gate in CI

```sh
opencomplai check --target NIST_AI_RMF --gate NIST_AI_RMF --gate-fail-on missing --repo-root .
```

The command exits `1` when a row reads `Missing`. A row that reads `Unverified` does not fail
it unless you set `--gate-fail-on unverified`. See
[Gating other frameworks](../cli/check.md#gating-other-frameworks).

## What stays attested and why

The 16 `organisational` rows are decisions about people and process that no file or scan in a
repository can show. They read `Unverified` until the provider records an attestation; the
statement is recorded verbatim and nothing checks it. The attestation account follows in the
EU projection section.

## EU projection account

This section keeps the account of how EU AI Act evidence is re-projected.

### How the re-projection works

1. `opencomplai check`/`gaps` computes a per-EU-AI-Act-article
   `Met`/`Partial`/`Missing`/`Unverified` status from your rule engine, obligation
   catalogue, code scan and pipeline evaluator results: the ordinary `GapReport`
   (`opencomplai_core.gap_report`).
2. `data/nist_ai_rmf_subcategories.json` holds the 72 subcategories of the RMF 1.0
   core (Govern/Map/Measure/Manage, outcome text as published in NIST AI 100-1). Each
   one lists, under `eu_ai_act`, the EU AI Act articles whose evidence covers it, each
   with a mapping `confidence` (`low` or `medium`; nothing claims `high`) and a short
   note on why.
3. `opencomplai_core.nist_rmf_report.build_nist_rmf_report` walks every subcategory and:
   - looks up the `GapReport` status of each mapped article;
   - reports the **worst** status among them (the same worst-case rollup
     `principle_report.py` uses for the 6 EU Trustworthy AI principles),
   - from 0.16.0, counts a link at `low` confidence whose article reads
     `Missing` or `Partial` as `Unverified` in that rollup, so only a link at `medium`
     confidence or better can make a subcategory `Missing` or `Partial` (the rationale
     names the capped article and keeps the article's own status in its citation), and
   - reports the **lowest** mapping confidence among them, never upgraded.

The mapping is per subcategory: `MAP 2.3` (data collection and selection) follows
Art. 10, while `MAP 2.1` (tasks and methods) follows Art. 11. When a mapped article
was not part of a given run's `GapReport`, the subcategory is `Unverified` with no
confidence, not a guessed verdict.

### Subcategories the EU AI Act evidence does not cover

From 0.16.0, 19 subcategories take an attestation (15 until then). 18 have an empty `eu_ai_act` list, because nothing
the tool gathers for the EU AI Act speaks to them: GOVERN 1.6, 1.7, 3.1 and 4.1; MAP 1.2,
1.3, 1.4 and 3.1; MEASURE 1.3, 2.2, 2.12, 2.13, 3.2, 3.3, 4.1 and 4.2; and MANAGE 2.1 and
3.2. For four of them (GOVERN 1.6, MEASURE 1.3, MEASURE 2.12 and MANAGE 3.2) the nearest
article exists but does not decide the question: registration under Art. 49 is no
inventory, the conformity route of Art. 43 is internal control for most Annex III systems,
and the energy disclosure and the duty to inform downstream providers bind only providers
of general-purpose AI models. The nineteenth, GOVERN 2.2, maps only to Art. 4, and Art. 4
is itself decided by an attestation, so no scan or check can speak to it either. They read
`Unverified` until the provider records an attestation:

```json
{
  "compliance_targets": ["EU_AI_ACT", "NIST_AI_RMF"],
  "framework_inputs": {
    "NIST_AI_RMF": {
      "attested": {
        "NIST_AI_RMF:MANAGE 2.1": {
          "statement": "Resourcing and non-AI alternatives are reviewed each quarter.",
          "attested_by": "Jane Doe",
          "attested_at": "2026-11-02"
        }
      }
    }
  }
}
```

An attested subcategory reads `Met` with confidence label `attested`; the statement is
recorded verbatim and nothing checks it. A subcategory that has EU AI Act evidence
takes no attestation: closing the EU AI Act gap is what changes it.

From 0.16.0, a subcategory also falls back to an attestation when no article
mapped to it gives evidence in the run, because each one is decided by an attestation
or does not apply. An article that applies only to some roles or tiers (for example
Art. 9, Art. 17 or Art. 26) counts as not applicable when a recorded checker session
does not list the duty it depends on. Then the row reads `Unverified` until it is
attested, never `Met` by default, and its rationale names the articles that do not
apply. If at least one mapped article does apply, that article decides the row on its
own and an attestation for the row is not used; the rationale says so.

Only a subcategory mapped to an article that always applies (Art. 5, 6, 12, 13, 14, 15
or 25) refuses an attestation outright: `gaps` and `check` exit `2` if you record one.
Every other subcategory accepts it, so it can be recorded before any checker session
exists, but it counts only in a run where every mapped article is not applicable or
decided by an attestation.

An attestation of EU AI Act Art. 4 does not carry over. An EU row that an attestation
decides counts as no evidence for NIST, so GOVERN 2.2 stays `Unverified` until it has its
own attestation, and MAP 3.4 (Art. 4 and Art. 26) holds at `Unverified` at best while
Art. 26 applies, because its Art. 4 part is never counted; its rationale says that Art. 4
was set aside. From 0.16.0, where a recorded checker session shows that Art. 26
does not apply, the row takes an attestation and reads `Met` once one is recorded.

From 0.16.0, Art. 20 (corrective actions) is decided by an attestation as well,
so it is set aside in the same way. MANAGE 2.3 and MANAGE 2.4 hold at `Unverified` at best
while Art. 20 applies, as MAP 3.4 does while Art. 26 applies. MANAGE 2.4 keeps Art. 14 (the stop and override
control) as its medium link, so it can still read `Missing` or `Partial`, but it cannot
read `Met` while Art. 20 applies. Art. 20 applies only to the provider of a high-risk
system: where a recorded checker session shows it does not, it drops out and both rows
read from their other articles, so MANAGE 2.4 reads `Met` when Art. 14 is `Met`.

### Reading a subcategory row

```text
$ opencomplai gaps --manifest system-manifest.json --target NIST_AI_RMF

Subcategory   Status       Mapping conf.   From (EU AI Act)   Rationale
GOVERN 1.2    UNVERIFIED   low             Art. 17            Re-projected via
                                                               data/nist_ai_rmf_subcategories.json
                                                               (mapping confidence=low)
                                                               from existing EU AI Act
                                                               evidence: Art. 17 -> missing
                                                               (source=obligation,
                                                               evidence=provider_qms).
                                                               Capped at Unverified,
                                                               because a low-confidence
                                                               link cannot make a
                                                               subcategory Missing or
                                                               Partial: Art. 17.
```

Art. 17 is missing here, but its link to GOVERN 1.2 is only at `low` confidence, so the
row reads `UNVERIFIED` from 0.16.0 on and the rationale says it was capped.

Every re-projected row's `Rationale` names the exact EU AI Act article(s), their
gap-report status, and the evidence reference (rule id, obligation id, evaluator id or
scan finding) the verdict was derived from: the citation trail. `--output json`
carries the same fields under `nist_rmf_report.subcategories[].source_eu_ai_act_articles`
on both `opencomplai gaps --target NIST_AI_RMF` and `opencomplai check --with-gaps` (the
latter when `NIST_AI_RMF` is one of its resolved targets: `--target`, else the
manifest's `compliance_targets`, else its `compliance_target`).

### Alongside the EU AI Act

`NIST_AI_RMF` can be the only target (the manifest's `compliance_target`, or `gaps
--target NIST_AI_RMF`), which prints the subcategory table above. It can also sit next
to the EU AI Act, in the manifest's `compliance_targets` or with repeated `--target`.

Then `gaps` prints the EU AI Act table and a NIST AI RMF requirement table, and
`gaps --output json` and `check --with-gaps` also carry a NIST AI RMF framework report
(`frameworks` / `framework_reports`) next to `nist_rmf_report`. Its rows have ids
prefixed `NIST_AI_RMF:`, source `crosswalk` (or `attestation` for an attested row), and
`derived_from: "EU_AI_ACT"`. Any requirement can be excluded with a reason under
`framework_inputs.NIST_AI_RMF.excluded`. Being derived, NIST AI RMF adds no controls
and no `recommend` files. It gates `check` only if you opt in (see
[Gating other frameworks](../cli/check.md#gating-other-frameworks)).

### Honesty guarantees

- **`needs_founder_review` is always `true`.** The mapping has not been confirmed by a
  human compliance or legal reviewer.
- **Confidence never gets upgraded.** A subcategory mapped at `low` confidence is
  reported at `low`, however "measured" the underlying EU AI Act evidence is.
  `confidence_label` is always `heuristic_estimate` for a re-projected verdict, never a
  legal determination.
- **A weak link never fails a subcategory.** From 0.16.0, a link at `low`
  confidence cannot make a subcategory `Missing` or `Partial`: it reads `Unverified`
  and is cited as supporting evidence, so a doubtful link in the mapping cannot fail
  `check --gate NIST_AI_RMF` on its own. A `Met` or `Unverified` result is never
  capped.
- **An uncovered subcategory is `Unverified`, never fabricated.** If no article maps to
  it and no attestation is recorded, or the mapped articles are not in the current run,
  the verdict says exactly that instead of guessing.
- **Links to ISO/IEC 42001 and ISO/IEC 27090 compute no verdict.** Each subcategory also
  lists related ISO/IEC 42001 rows (from NIST's own crosswalk) and ISO/IEC 27090 rows;
  see [Framework mappings](../frameworks/mappings.md). Those frameworks are assessed
  separately as the attestation-led `ISO_IEC_42001` and `ISO_IEC_27090` targets.
- **The EU AI Act `Mapped` column is a summary.** `data/framework_crosswalk.json` still
  cites one NIST category and one ISO/IEC 42001 clause per EU AI Act article in the
  default `gaps` output and the dossier. It does not decide NIST verdicts.

### A living framework

NIST AI RMF 1.0 (NIST AI 100-1, published January 2023) is the version this taxonomy
tracks. The White House's "America's AI Action Plan" (2025) directed NIST to revise
the AI RMF to remove references to misinformation, diversity/equity/inclusion, and
climate change; that revision had not been published when the taxonomy was last
checked (see `data/nist_ai_rmf_subcategories.json`'s `_meta.researched_at` and
`_meta.pending_revision_caveat`). `GOVERN 3` (workforce diversity/equity/inclusion) and
`MEASURE 2.12` (environmental impact) are the subcategories most likely to move if and
when that revision publishes. Re-verify the taxonomy against NIST's current core
tables before treating it as durable reference material.

### Where this lives in the codebase

| Concern | File |
|---|---|
| RMF 1.0 subcategories and their mapping | `packages/core/src/opencomplai_core/data/nist_ai_rmf_subcategories.json` |
| Loader | `packages/core/src/opencomplai_core/nist_ai_rmf_subcategories.py` |
| Re-projection and attestations | `packages/core/src/opencomplai_core/nist_rmf_report.py` |
| Registry entry (derived pack) | `packages/core/src/opencomplai_core/frameworks.py` |
| EU AI Act `Mapped` column summary | `packages/core/src/opencomplai_core/data/framework_crosswalk.json` |
| CLI surface | `opencomplai gaps --target NIST_AI_RMF`, `opencomplai check --with-gaps` |

See [Control Codes → Principles → Articles](eu-ai-act-principles.md) for the EU AI Act
evidence this page's verdicts are derived from, and run `opencomplai gaps --target
NIST_AI_RMF` against your own manifest to see the re-projection applied to your system.

## Review status

`needs_founder_review` is `true` for all 72 rows: the mapping has not been confirmed by a
human reviewer, and `confidence_label` is `heuristic_estimate` for every re-projected
verdict. Confidence is never upgraded.

## Disclaimer

This page describes what the tool checks. It is not legal advice and gives no presumption of
conformity. A `Met` row is the tool's reading of evidence, not a finding by an assessor.
