# Data protection impact assessment

Working draft for Article 35, completed for Example Ltd.

<!-- clause: processing -->
## Processing and its purpose

Example Ltd processes support ticket text, names and email addresses in its service desk system, in order to answer customer requests.

<!-- clause: necessity -->
## Necessity and proportionality

The processing is necessary to answer requests. It is proportionate because data minimisation applies: only name, email and ticket text are kept, and no less intrusive route would work.

<!-- clause: risks -->
## Risks to people

| Risk to individuals | Likelihood | Severity | Safeguard | Residual risk |
| --- | --- | --- | --- | --- |
| Unwanted disclosure of ticket text | Low | Medium | Encryption and access control | Low |
| Wrong data shown to an agent | Medium | Low | Role based views | Low |

<!-- clause: measures -->
## Safeguards and measures

Measures: encryption at rest, access control by role, pseudonymisation of exports and a yearly access review.

<!-- clause: consultation -->
## Consultation or reason not consulted

The data protection officer and the service desk processor were consulted in January 2026. Data subjects were not consulted because the processing is routine.

<!-- clause: special-categories -->
## Special categories of data

No special categories or criminal-offence data are processed. Agents are told not to record them in tickets.

<!-- clause: automated-decisions -->
## Automated decisions and profiling

Tickets are ranked automatically, but no decision with legal or similar effect is taken. An agent reviews every ranked ticket.
