# AI system impact assessment

Example Ltd, ticket ranking system. Clause comments kept.

<!-- clause: 5.2 -->
## 5.2 Documenting the process
Our written assessment process is kept current by the governance team and every owner can find the procedure.

<!-- clause: 5.4 -->
## 5.4 Timing of AI system impact assessment
An assessment is triggered at each life-cycle stage and again before any major change to the ranking model.

<!-- clause: 5.5 -->
## 5.5 Scope of the AI system impact assessment
The scope covers the ticket ranking system and its uses; the billing tools are out of scope for this review.

<!-- clause: 5.6 -->
## 5.6 Allocating responsibilities
The service owner holds the role of assessor and the risk lead has the authority to review and sign-off each result.

<!-- clause: 5.7 -->
## 5.7 Establishing thresholds for sensitive uses, restricted uses and impact scales
Uses touching minors are restricted; a severity scale of low, medium and high rates every impact and sets the threshold.

<!-- clause: 5.10 -->
## 5.10 Recording and reporting
Results are recorded in the register and the report is shared with the board and the stakeholders who asked for it.

<!-- clause: 5.11 -->
## 5.11 Approval process
The head of operations gives approval and the record shows who signed off, with the date, on each assessment.

<!-- clause: 5.12 -->
## 5.12 Monitoring and review
We review each assessment every quarter and after each change, and we monitor whether the process still works.

<!-- clause: 6.2 -->
## 6.2 Scope of the AI system impact assessment
This assessment covers the ticket ranking system, its current uses and the period from January to December.

<!-- clause: 6.3 -->
## 6.3 AI system information
The purpose is to rank support tickets; intended use is triage and a misuse such as automatic refusal is not intended.

<!-- clause: 6.4 -->
## 6.4 Data information and quality
The system relies on three years of ticket data, and we run quality checks for bias and completeness on that data.

<!-- clause: 6.5 -->
## 6.5 Algorithm and model information
The model is a gradient boosted classifier that our own team trained on labelled tickets with a documented algorithm.

<!-- clause: 6.6 -->
## 6.6 Deployment environment
The system is deployed in the cloud for agents in two countries; languages are English and French with a latency constraint.

<!-- clause: 6.7 -->
## 6.7 Relevant interested parties
Affected people are customers who write in; other stakeholders include agents, the legal team and the regulator.

<!-- clause: 6.8.2 -->
## 6.8.2 Benefits and harms
The benefits are faster replies for customers, while the harms include urgent tickets being ranked too low by mistake.

<!-- clause: 6.8.3 -->
## 6.8.3 AI system failures and reasonably foreseeable misuse
If the ranking fails, urgent tickets wait longer; a foreseeable misuse is gaming the subject line to jump the queue.

<!-- clause: 6.9 -->
## 6.9 Measures to address harms and benefits
We chose measures to reduce harm, such as a manual override, and the service owner tracks each action until it is done.
