# Major ICT-related incident: classification and report outline

Owner: Example Ltd, Head of Technology Risk
Incident reference: INC-2026-004

Outline for Articles 17 to 19, filled in for a fictional exercise at Example Ltd.

<!-- clause: classification -->
## Classification of the incident

Which criteria and thresholds did you apply, and what was the result?

We applied the severity criteria in our incident policy: clients affected, duration and data loss. The payment portal was down for 3 hours and the materiality threshold was met, so the incident was classified as major.

<!-- clause: initial-notification -->
## Initial notification to the authority

When was the authority told, by whom, and what did the notice contain?

The initial notification went to the supervisor within four hours of classification, sent by the incident manager. It named the affected service, the time of detection and the first impact estimate.

<!-- clause: intermediate-report -->
## Intermediate report

What status updates and recovery steps were sent, and when?

An intermediate report followed after 72 hours with a status update, the recovery steps taken and the open actions.

<!-- clause: final-report -->
## Final report

What was the root cause, the impact and the corrective action?

The final report gave the root cause (an expired certificate on a load balancer), the impact on clients and the corrective action: automated certificate renewal and an expiry alert.

<!-- clause: client-information -->
## Information to affected clients

Which clients were affected, how were they informed, and what protective steps were shared?

All customers using the payment portal were informed by email and on the status page, and we communicated that no data was lost and no action was needed on their side.
