# Post-Market Monitoring Plan: Art. 72

**Gap source:** probe (`post_market_monitoring_plan`)
**Why this was generated:** plan on file
**Template:** `pmm-plan`

## Where this file must live

Save the filled plan as `docs/post-market-monitoring-plan.md` so `opencomplai gaps` can find it.
This plan covers the Example Ltd hiring-screen model.

## Scope

- System and versions covered: Version 2 of the Example Ltd hiring-screen model.
- Deployments or customers in scope: Two customer deployments in the UK.

## Data to collect and from where

- Performance and accuracy data: Monitor accuracy and drift from the weekly evaluation job.
- User feedback and complaints: Complaints arrive through the support inbox and are logged.
- Other sources (logs, audits, third-party reports): Audit notes and third-party reports.

## Review cadence

- How often the collected data is reviewed: The team reviews the monitoring data every month.
- Who attends the review: Engineering lead and support lead.

## Owner

- Person or team that owns this plan: The head of engineering owns this plan.

## Triggers for corrective action

- What findings lead to a fix, a rollback or a risk-register update: An accuracy drop of five points leads to a rollback and a risk-register update.

## Links

- Risk register (path): docs/risk-register.md
- Serious-incident log (`incident-log.json` at the repository root): Not yet opened; no incident has occurred.

## Traceability

This template was generated because `opencomplai gaps` reported **Art. 72** as
**Partial**, sourced from probe `post_market_monitoring_plan`.
