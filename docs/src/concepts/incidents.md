# Incidents

`opencomplai incident` keeps a local register of serious incidents (Art. 73) and a signed log of every
change to it. It watches notification deadlines for you. It does not file anything, and it does not decide
whether an event is a reportable incident.

!!! warning "Deadlines are provisional"
    The day counts below are shipped as data with `confidence: low` and `needs_founder_review: true`. They
    are the author's unverified reading, marked "lawyer to confirm". They are a working aid, not a statement
    of the legal period. Confirm the applicable period yourself.

## Two files

| File | What it is |
|---|---|
| `incident-register.json` | The current state: one record per incident (declaration, awareness time, class, notifications, closure). Free text such as the description and closure note stays here. |
| `incident-log.json` | An append-only, hash-chained, signed log. Each `declare`, `classify`, `notify` and `close` adds one entry of structured fields only (ids, class, timestamps, party kind, name and reference). No free text. |

The commands are described in [`incident`](../cli/incident.md). The log is checked with
`opencomplai verify incident-log.json --kind incident-log` ([`verify`](../cli/verify.md)): exit `0` when the
chain and signatures hold, `1` when entries are unsigned or the log was edited, reordered or shortened in
the middle. Dropping the newest entries is only detectable against a head you stored elsewhere.

`declare` and `close` also move the system state (`running` to `incident_mode` and back). The log entry is
written first, so a refused state change never loses the entry.

## Deadline clocks

A clock runs from the **awareness time** you record, not from the declaration time. Its length depends on
the incident class:

| Class | Days from awareness |
|---|---:|
| `death` | 10 |
| `critical_infrastructure` | 2 |
| `widespread_infringement` | 2 |
| `health_harm` | 15 |
| `fundamental_rights` | 15 |
| `property_environment` | 15 |
| `unclassified` | no clock |

Each of these rows is stored with:

- `source`: `Regulation (EU) 2024/1689 Art. 73 (reading unverified)`
- `confidence`: `low`
- `needs_founder_review`: `true`
- `note`: "Proposed day count; lawyer to confirm." (for `unclassified`: no clock until the incident is
  classified)

An incident with no class has no deadline. The first `authority` notification decides whether the deadline
was met.

## No scheduler

Nothing here runs in the background. A deadline, a "due soon" state (within 24 hours) and an "overdue"
state are computed at the moment you ask, from the register and the time of the question, through an
injected clock. `OPENCOMPLAI_NOW` fixes that time for tests and CI. `incident export` shows the absolute
deadline and prints no current date, state or relative days, so the same record always exports the same
bytes.

## Evidence in the gap report

An `incident-log.json` in the repository root, and a post-market monitoring plan file, are the evidence
Arts. 72 and 73 read in the gap report. Both rows stay at `partial` at most, and the incident log
also feeds QMS clauses (h) and (i). A log that exists is evidence that
a process runs, not that it works.

## What leaves your machine

The register's free text never leaves it. The scan artifact can carry an `incidents` summary of leaf
values only (incident id, class, open or closed, dates, party kinds and counts); see [Published schemas](published-schemas.md). The
templates for an authority report and a downstream notice (`incident template`) are drafts: low
confidence, flagged for founder review, and not legally reviewed.
