# agents

Offline view of the agent inventory declared in the system manifest: list the
agents, validate the declaration, cross-check it against a scan, and print a
report that includes a responsibility map.

**What:** the manifest's `agent_inventory` block (agents, tools, models,
mandate, delegation, guardrails, logging) made readable and checkable from the
command line.

**When:** after you have declared an agent inventory in `system-manifest.json`,
and optionally after `opencomplai check --scan` has written a scan report.

**Offline:** every `agents` subcommand reads local files only. None of them
needs `OPENCOMPLAI_VAULT_URL` or a network connection.

!!! warning "Draft content awaiting founder review"
    The responsibility map printed by `agents report` is draft reference
    content. Every row is low confidence and flagged `needs_founder_review`;
    the wording is unverified and a lawyer is to confirm it. It is not a legal
    determination of who owes what.

All three commands print evidence only. None of them gives a compliance
verdict.

## Common options

| Option | Meaning |
| --- | --- |
| `--manifest`, `-m` | System manifest JSON (default `system-manifest.json`) |
| `--scan-report` | Optional scan report JSON from `opencomplai check --scan`. A file that cannot be parsed is a warning, not a failure |

## `agents inventory`

Print the agent tree with each agent's tools, models and whether it declares a
mandate. A manifest without an inventory prints `no agent inventory declared`
and exits `0`.

=== "macOS / Linux"
    ```bash
    opencomplai agents inventory -m system-manifest.json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai agents inventory -m system-manifest.json
    ```

`--output-format`, `-o` takes `human` (default) or `json`.

## `agents check`

Validate the declared inventory (dangling parents, parent cycles, dangling
delegates, delegation depth, unknown tool references) and, when a scan report is
given, cross-check what the manifest declares against what the scan detected.
Each finding is labelled `declared` or `detected`.

=== "macOS / Linux"
    ```bash
    opencomplai agents check -m system-manifest.json --scan-report scan-report.json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai agents check -m system-manifest.json --scan-report scan-report.json
    ```

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | No findings |
| `1` | Declared-versus-detected findings from the cross-check |
| `2` | Missing or invalid manifest, or an invalid inventory (the offending agent id is printed) |

The scan side is heuristic: a finding in test, docs, generated or vendor code
is ignored, and provider names are matched by containment. Treat a finding as
a prompt to look, not as a result.

## `agents report`

Print the inventory, the findings and the responsibility map: the manifest's
own `responsibility_map` (recorded verbatim) and the draft reference rows, each
with `confidence` and `needs_founder_review`. General-purpose model duties
(Art. 53 and Art. 55) are attributed to the upstream model provider, never to
the customer.

=== "macOS / Linux"
    ```bash
    opencomplai agents report -m system-manifest.json --format markdown --output agents-report.md
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai agents report -m system-manifest.json --format markdown --output agents-report.md
    ```

| Option | Meaning |
| --- | --- |
| `--format` | `markdown` (default) or `json` |
| `--output` | Write to this file instead of stdout |

The report carries no timestamp, so the same inputs produce the same bytes.
