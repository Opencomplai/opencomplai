# agents

Offline view of the agent inventory declared in the system manifest: list the
agents, validate the declaration, cross-check it against a scan, and print a
report that includes a responsibility map. Four more subcommands sign a mandate
attestation, verify an agent decision log, and read the audit log of another
tool.

**What:** the manifest's `agent_inventory` block (agents, tools, models,
mandate, delegation, guardrails, logging) made readable and checkable from the
command line, plus the signed statements and logs that go with it.

**When:** after you have declared an agent inventory in `system-manifest.json`,
and optionally after `opencomplai check --scan` has written a scan report.

**Offline:** every `agents` subcommand reads local files only. The one
exception is `agents verify-log --vault`, which sends events to the evidence
vault and so needs `OPENCOMPLAI_VAULT_URL`; nothing else does.

| Subcommand | Use |
| --- | --- |
| [`agents inventory`](#agents-inventory) | Print the agent tree |
| [`agents check`](#agents-check) | Validate the inventory and cross-check a scan |
| [`agents report`](#agents-report) | Print inventory, findings and responsibility map |
| [`agents attest`](#agents-attest) | Sign a statement about one agent's mandate hash |
| [`agents verify-log`](#agents-verify-log) | Verify an agent decision log |
| [`agents import-log`](#agents-import-log) | Summarise a runtime audit log |
| [`agents dispute-report`](#agents-dispute-report) | Render what each agent was told and decided |

!!! warning "Draft content awaiting founder review"
    The responsibility map printed by `agents report` is draft reference
    content. Every row is low confidence and flagged `needs_founder_review`;
    the wording is unverified and a lawyer is to confirm it. It is not a legal
    determination of who owes what.

All seven subcommands report or sign evidence only. None of them gives a
compliance verdict.

## Common options

These apply to `inventory`, `check` and `report`. `attest` and `verify-log` take
`--manifest` too and list it in their own tables.

| Option | Meaning |
| --- | --- |
| `--manifest`, `-m` | System manifest JSON (default `system-manifest.json`) |
| `--scan-report` | Optional scan report JSON from `opencomplai check --scan`. A file that cannot be parsed is a warning, not a failure |
| `--output-format`, `-o` | `inventory` and `check` only: `human` (default) or `json` |

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

Expired agent mandates are listed after the findings (and in the `expired_mandates`
key of `-o json`) with the agent id and the `expires_at` value. The rule is the
one `gaps` uses: the UTC calendar date, so the expiry day itself is not expired.
Expired mandates are not counted as findings and do not change the exit code.

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

## `agents attest`

Sign a statement that the holder of a key vouches for one agent's mandate hash
until an expiry. The hash is a SHA-256 over the mandate declared in the manifest,
so a later edit to the mandate no longer matches. Check the file with
[`verify`](verify.md) and kind `agent-attestation`.

=== "macOS / Linux"
    ```bash
    opencomplai agents attest -m system-manifest.json --agent-id support-bot --issuer "Compliance team"
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai agents attest -m system-manifest.json --agent-id support-bot --issuer "Compliance team"
    ```

| Option | Default | Meaning |
| --- | --- | --- |
| `--manifest`, `-m` | `system-manifest.json` | System manifest JSON with an `agent_inventory` |
| `--agent-id` | required | Id of the agent to attest; it must declare a mandate |
| `--issuer` | required | Who is vouching: printable ASCII, up to 128 characters. Self-declared, not a verified identity |
| `--valid-days` | `30` | Days until the attestation expires, from `1` to `365` |
| `--out` | `agent-attestation-<agent_id>.json` | Output file. An existing file is never overwritten |
| `--key` | `~/.opencomplai/signing.key` | Private key PEM. `attest` always signs |
| `--output`, `-o` | `human` | `human` or `json` |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Attestation written |
| `2` | Missing or invalid manifest, no `agent_inventory` or an invalid one, unknown agent id, agent without a mandate, `--out` already exists, missing signing key, or an `--issuer` that cannot be signed |

An attestation is a signed statement, not a compliance claim: it says a key holder
signed that hash and nothing about whether the mandate is lawful or complete. See
[Agents](../concepts/agents.md#attestations).

## `agents verify-log`

Check an agent decision log (JSON lines): the hash chain, the signatures, and, from
the manifest's inventory, which entries were outside the declared mandate. The
log's own flag is never trusted. A missing default manifest is not an error: the
chain and signatures are still checked and the output says the mandate was not
checked.

=== "macOS / Linux"
    ```bash
    opencomplai agents verify-log agent-log.jsonl -m system-manifest.json --require-signed
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai agents verify-log agent-log.jsonl -m system-manifest.json --require-signed
    ```

| Option | Default | Meaning |
| --- | --- | --- |
| `path` (argument) | required | Agent decision log, JSON lines |
| `--manifest`, `-m` | `system-manifest.json` | System manifest with an `agent_inventory`. A manifest you name that is missing exits `2` |
| `--pub-key` | `~/.opencomplai/signing.pub` | Public key PEM used to check signatures |
| `--require-signed` | off | Fail when entries are unsigned, or signed but the key cannot verify them |
| `--expected-head` | *(none)* | Chain head you stored earlier; a different head fails |
| `--expected-count` | *(none)* | Entry count you stored earlier; a different count fails |
| `--vault` | off | Append one `agent_action` event per entry to the evidence vault. Needs `OPENCOMPLAI_VAULT_URL`. The event carries ids, hashes and reason codes only; the whole log entry, including any `intent`, `input_hash` and `outcome` it holds, is first stored in the vault object store |
| `--vault-from-seq` | `1` | With `--vault`: first entry number to send, to resume a partial run |
| `--system-id` | manifest's | With `--vault`: system id to put on the events. Required when there is no manifest |
| `--output`, `-o` | `human` | `human` or `json` |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Chain verified and no entry outside the mandate |
| `1` | Tampered or broken chain, an entry outside the mandate, an empty log, or signatures that could not be verified under `--require-signed` |
| `2` | Bad input: unreadable log, invalid manifest, missing public key file, `--vault` without `OPENCOMPLAI_VAULT_URL`, or a vault request that failed |

The output ends with `head=<sha256> count=<n>`. A hash chain cannot show that the
newest entries were removed, so store that line elsewhere and pass it back with
`--expected-head` and `--expected-count` to catch truncation. `--vault` has no
cursor or de-duplication: running it again appends the same events again, so use
`--vault-from-seq` to resume. A log that fails the chain check is never sent.
Mandate rules are described in [Agents](../concepts/agents.md#what-verify-checks).

## `agents import-log`

Read an audit log that an agent runtime governance toolkit wrote as JSON lines and
summarise it: line counts, rejected lines, an integrity label and the evidence
status. Read-only; nothing feeds `check`, `gaps` or a dossier.

=== "macOS / Linux"
    ```bash
    opencomplai agents import-log audit.jsonl --format json --output import-summary.json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai agents import-log audit.jsonl --format json --output import-summary.json
    ```

| Option | Default | Meaning |
| --- | --- | --- |
| `file` (argument) | required | Audit log, JSON lines. One file, no globs |
| `--source` | `agt` | Log format. Only `agt` is supported |
| `--map` | built-in preset | Override where a field is read from, such as `--map ts=data.when`. Repeatable. Fields: `ts`, `agent_id`, `action`, `decision`, `rule`, `told`, `approver` |
| `--format` | `human` | `human` or `json` |
| `--output` | stdout | Write to this file instead |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | The file was read. Rejected lines and an `UNVERIFIED` status are reported, never fatal |
| `2` | Unreadable input, a bad `--map` or `--source`, or an unwritable `--output` |

Imported evidence is capped at PARTIAL and never reads Met. The field mapping is a
low-confidence preset: check it against your own records with `--map`. See
[Agent audit-log import](../concepts/agt-import.md).

## `agents dispute-report`

Render, for a date window, what each agent was told, what was decided and why,
from an audit log of another tool or a native agent decision log. Evidence only.

=== "macOS / Linux"
    ```bash
    opencomplai agents dispute-report --log audit.jsonl --from 2026-01-01 --to 2026-01-31 --output dispute.md
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai agents dispute-report --log audit.jsonl --from 2026-01-01 --to 2026-01-31 --output dispute.md
    ```

| Option | Default | Meaning |
| --- | --- | --- |
| `--log` | required | Audit log, JSON lines |
| `--from` | required | Window start, an ISO date or datetime |
| `--to` | required | Window end, inclusive; a date means the whole day |
| `--source` | `agt` | `agt` or `native`. `--map` applies to `agt` only |
| `--agent` | all agents | Only this agent id |
| `--map` | built-in preset | Override where a field is read from, as in [`agents import-log`](#agents-import-log). Repeatable |
| `--format` | `markdown` | `markdown` or `json` |
| `--output` | stdout | Write to this file instead |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | The file was read and the report written, even with rejected lines |
| `2` | Unreadable log, a bad `--from`/`--to` window or `--map`, or an unwritable `--output` |

Imported evidence is capped at PARTIAL. The report states what the log recorded; it
does not decide who is responsible.
