# Agents

A system built from AI agents is described in the manifest's `agent_inventory` block. Opencomplai records
that declaration, checks it for internal consistency, compares it with what a scan detected, and can sign
and later verify statements about it. It never decides whether an agent is lawful or compliant.

## The inventory

The inventory is the provider's own declaration. Each agent has an `id` and a `name`, and may carry:

| Part | What it records |
|---|---|
| Tools | Tool names with a kind (`mcp`, `function` or `api`), scope, whether it has side effects and whether it needs approval. |
| Models | The provider and model the agent calls. |
| Mandate | What the agent may and may not do (`permitted_actions`, `prohibited_actions`, `limits`), who granted it, and an optional expiry and review cadence. |
| Delegation | Which agents it may hand work to, and how deep. |
| Guardrails | A list of guardrail kinds, each with an optional evidence reference. |
| Logging | Where the agent's decision log lives and whether it captures intent. |

A tool in a mandate is written `tool:<name>` and must name a tool declared by the same agent. The block can
also carry a `responsibility_map`, which is free text the provider writes and the tool records verbatim.

[`opencomplai agents`](../cli/agents.md) lists the inventory, validates it (dangling parents, cycles,
dangling delegates, unknown tool references), cross-checks it against a scan report, and renders a report.
Every findings line is labelled `declared` or `detected`; the scan side is heuristic, so a finding is a
prompt to look, not a result.

## Responsibility

`agents report` also prints a draft reference map of which duties sit with the upstream general-purpose
model provider, with the customer, or are shared. Every row carries `source`, `confidence` and
`needs_founder_review`, the wording is unverified, and a lawyer is to confirm it. It is not a legal
determination of who owes what.

## What reaches the gap report

The manifest's agent inventory feeds Articles 12, 14, 15 and 26 of the gap report. It can lift a row to
`partial` at most, never `met`, and nothing changes for a manifest with no inventory. Scan findings alone
never produce `met` for an agent framework.

## Attestations

`opencomplai agents attest` signs one statement: the holder of a key vouches for one agent's mandate hash
until an expiry. The mandate hash is a SHA-256 over the declared mandate, so any later edit to the mandate
no longer matches.

!!! note "A signed record, not an assessment"
    An attestation says a key holder signed that hash. It makes no compliance claim, carries no legal
    wording, and says nothing about whether the mandate is lawful or complete. The issuer is a printable
    ASCII string the signer chose; it is self-declared, not verified identity.

Attestations are created and checked offline and are never uploaded by the CLI.

## What `verify` checks

[`opencomplai verify`](../cli/verify.md) dispatches by `--kind`. Two kinds belong to agents:

| Kind | Checks |
|---|---|
| `agent-attestation` | The signature, the expiry (as of now, or `--expect now=<ISO UTC>`), and optionally that the mandate hash equals `--expect mandate_sha256=...`. |
| `agent-log` | The hash chain and signatures of an agent decision log. |

`opencomplai agents verify-log` does the log check with more detail: it recomputes from the declared
mandate which entries were outside it, and never trusts the log's own `outside_mandate` flag. Mandate
expiry is judged against each entry's own timestamp, never against the clock. `mandate.limits` is not
evaluated. Those mandate rules are design choices of the tool, flagged low confidence and for founder
review, not rules taken from a standard.

A hash chain cannot show that the newest entries were removed. The output ends with `head=<sha256>
count=<n>`; store it elsewhere and pass `--expected-head` and `--expected-count` to catch truncation.

`agents import-log` and `agents dispute-report` cover logs written by other tools; see
[Agent audit-log import](agt-import.md).

## What leaves your machine

Only counts and a chain flag and head go into the scan artifact's `agents` summary: how many agents, how
many with a mandate, how many with guardrails, and, when a log was verified, the entry count, the
out-of-mandate count, whether the chain was valid and its head hash. A dashboard shows these as reported by
the CLI and does not verify them.
