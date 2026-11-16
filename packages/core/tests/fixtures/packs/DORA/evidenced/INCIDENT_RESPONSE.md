# Incident response plan

Owner: Head of Engineering, Example Ltd
Last reviewed: 2026-09-01

## Detection and classification

- Alerts from monitoring detect most incidents; staff can also report one by email.
- The on-call engineer classifies each incident as low, medium or high severity within 30 minutes.

## Containment and recovery

- The first step is to contain the problem by isolating the affected service.
- The service is recovered from the latest good release and checked with the smoke tests.

## Roles and escalation

- The incident lead is the on-call engineer; the deputy is the platform lead.
- Unresolved high severity cases escalate to the security manager through the on-call rota.

## After the incident

- A review meeting is held within five working days and actions are tracked.
