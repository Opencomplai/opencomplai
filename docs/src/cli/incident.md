# incident

Record Art. 73 serious incidents locally and watch their notification deadlines.

**What:** a plain JSON register (default `incident-register.json`) with a record per
incident: declaration, awareness time, class, notifications sent and closure. Deadline
clocks are computed when you ask, from the awareness time and the class.

!!! warning "Deadlines are provisional"
    The day counts per class are low-confidence data, flagged `needs_founder_review`,
    pending review by the founder and a lawyer. Treat them as a working aid, not as
    legal advice, and confirm the applicable period yourself.

The register is a local current-state file. Each change is also appended to a signed
incident log (see below). The free-text `--description` and `--note` stay in the local
register and are never copied into the log.

Every subcommand takes `--file` / `-f` (default `incident-register.json`). Timestamps
are ISO 8601, stored in UTC (a timestamp without a zone is read as UTC). Misuse (unknown
id, awareness after declaration, closing twice, a bad timestamp) exits `2` and leaves the
register unchanged.

## `incident declare`

=== "macOS / Linux"
    ```bash
    opencomplai incident declare --system-id loan-decision-model \
      --description "Model returned another customer's record" \
      --aware-at 2026-03-01T08:00:00Z
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai incident declare --system-id loan-decision-model `
      --description "Model returned another customer's record" `
      --aware-at 2026-03-01T08:00:00Z
    ```

Prints the new id (`INC-0001`, then `INC-0002`, ...). `--system-id` may come from
`--manifest` (default `system-manifest.json`). `--declared-at` defaults to now and
`--aware-at` to the declaration time. `--class` is optional; an unclassified incident has
no deadline clock.

## `incident classify`

=== "macOS / Linux"
    ```bash
    opencomplai incident classify --id INC-0001 --class critical_infrastructure
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai incident classify --id INC-0001 --class critical_infrastructure
    ```

Classes: `unclassified`, `death`, `health_harm`, `critical_infrastructure`,
`fundamental_rights`, `property_environment`, `widespread_infringement`.

## `incident notify`

=== "macOS / Linux"
    ```bash
    opencomplai incident notify --id INC-0001 --party "Market Authority" --kind authority --ref REF-123
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai incident notify --id INC-0001 --party "Market Authority" --kind authority --ref REF-123
    ```

`--kind` is `authority`, `deployer`, `importer` or `distributor`; `--sent-at` defaults to
now. The first `authority` notification decides whether the deadline was met.

## `incident close`

=== "macOS / Linux"
    ```bash
    opencomplai incident close --id INC-0001 --note "Root cause fixed and verified"
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai incident close --id INC-0001 --note "Root cause fixed and verified"
    ```

## `incident status`

=== "macOS / Linux"
    ```bash
    opencomplai incident status --output json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai incident status --output json
    ```

Per incident: class, `deadline_at`, state, `hours_remaining` and whether it is closed.
States: `no_clock`, `open`, `due_soon` (within 24 hours), `overdue`, `met`,
`notified_late`. Options: `--id`, `--system-id`, `--output human|json`. Contacts listed
under `incident_contacts` in the manifest that have no notification yet are shown as
pending. Set `OPENCOMPLAI_NOW` to an ISO 8601 time to evaluate the clocks at a fixed
moment (tests and CI).

## `incident export`

=== "macOS / Linux"
    ```bash
    opencomplai incident export --id INC-0001 --format md --output incident-INC-0001.md
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai incident export --id INC-0001 --format md --output incident-INC-0001.md
    ```

`--format` is `md` (default) or `json`; without `--output` it prints to stdout. The
export shows the absolute deadline and carries no current date, state or relative days,
so the same record always exports the same bytes.

## Manifest field

```json
"incident_contacts": [
  {"kind": "authority", "party": "Market Authority", "contact": "incidents@authority.example"}
]
```

Optional; omitted from the manifest when empty.

## Incident log and verification

Every `declare`, `classify`, `notify` and `close` appends one entry to `incident-log.json`,
in the same directory as `--file` unless you pass `--log`. Entries are hash-chained and
signed with the key from `--key` (default `~/.opencomplai/signing.key`, or
`SIGNING_KEY_PRIVATE`). With no key the entry is written unsigned and a warning is printed.
Entries hold structured fields only (ids, class, timestamps, party kind, name and reference).

`declare` and `close` also move the system state: `running` to `incident_mode` on declare,
back to `running` on close. The log entry is written first. If the state change is refused
(for example declaring while the system is halted, or closing when no incident is open), the
entry stays in the log next to a `transition_rejected` entry, the state is unchanged, the
error is printed and the command exits `1`. If the log cannot be written the command exits
`2` and changes nothing. `--commit-ref` (default `HEAD`) is recorded with the state change.

```bash
opencomplai verify incident-log.json --kind incident-log --pub-key signing.pub
```

Exit `0` when the chain and signatures check out, `1` when entries are unsigned or the log
was edited, reordered or had an entry removed. The output ends with the log head and entry
count. Dropping the newest entries is only detectable against a head you stored elsewhere.

## `incident template`

=== "macOS / Linux"
    ```bash
    opencomplai incident template --kind authority --id INC-0001 --output report.md
    opencomplai incident template --kind downstream --id INC-0001 --party "Acme" --party-kind deployer
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai incident template --kind authority --id INC-0001 --output report.md
    opencomplai incident template --kind downstream --id INC-0001 --party "Acme" --party-kind deployer
    ```

Renders a draft report for the market surveillance authority (`--kind authority`) or a notice
for a deployer, importer or distributor (`--kind downstream`, which needs `--party`). Fields
come from the stored incident; anything missing reads `_not provided_`. Both templates are
drafts: low confidence, flagged `needs_founder_review`, and **not legally reviewed**. Confirm
the required content and the recipient with counsel before sending.
