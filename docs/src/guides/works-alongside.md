# Works alongside other tools

OpenComplAI is a CI gate plus an evidence trail for the EU AI Act. It is a tripwire over a declared manifest, not a legal opinion or certification.

## Who it is for

Teams that build, fine-tune or substantially modify AI systems and need a per-release EU AI Act check in CI. A retrain, a purpose change or a capability extension can make you a provider: `opencomplai check --change-context` exits `4` for those cases (see [exit codes](../cli/exit-codes.md)).

The CLI is offline by default. `opencomplai push` is the only command that uploads anything, and only when you run it.

It is not for teams that only use an AI product and need a vendor-risk or procurement workflow.

## Promptfoo

- **What it does:** an evaluation tool for testing model and prompt behaviour; see its own documentation.
- **What OpenComplAI adds:** `opencomplai check` exit codes and a signed compliance artifact, `opencomplai gaps`, an Annex IV dossier from `opencomplai docs generate` with honest placeholders, and `opencomplai controls`.
- **How to run both:** as separate CI steps. Neither reads the other's output.

## Microsoft Agent Governance Toolkit

- **What it does:** a toolkit for governing AI agents; see its own documentation.
- **What OpenComplAI adds:** `opencomplai check` exit codes and a signed compliance artifact, `opencomplai gaps`, an Annex IV dossier from `opencomplai docs generate` with honest placeholders, and `opencomplai controls`.
- **How to run both:** as separate CI steps. The toolkit does not read OpenComplAI output; the optional log preview is described under What is not built.

## GRC platforms

- **What it does:** a governance, risk and compliance platform tracks policies, risks and evidence across a business; see its own documentation.
- **What OpenComplAI adds:** `opencomplai check` exit codes and a signed compliance artifact, `opencomplai gaps`, an Annex IV dossier from `opencomplai docs generate` with honest placeholders, and `opencomplai controls`.
- **How to run both:** as separate CI steps. To put the results in the platform, attach `compliance-artifact.json`, the `opencomplai gaps` output and the dossier by hand.

## What is not built

No bridge or importer to Promptfoo or any GRC platform is built; you move files by hand.

A preview log import exists for that toolkit: run `opencomplai agents import-log` (and `opencomplai agents dispute-report` for a per-agent window report). It reads files written by the Agent Governance Toolkit file audit sink, offline, as a preview. Imported evidence is capped at Partial and labelled "format-valid, not verified". The exit codes of `opencomplai check` and `opencomplai gaps` are unchanged, and nothing is pushed to or pulled from that toolkit. See [AGT log preview](../concepts/agt-import.md).

The export paths that exist are `opencomplai scan --sarif-output`, the `opencomplai check` JSON artifact, and `opencomplai push` to the OpenComplAI dashboard.

## When an accepted high-risk system exits 0

Accepting a classification does not make `opencomplai check` pass by itself. After `opencomplai accept` records it, the Art. 6 high-risk row no longer fails the check, but every other EU AI Act row still counts: `check` exits `0` only when no other EU AI Act row is Missing, and exits `1` with the Missing ids otherwise. The accepted system in the [gate demo](https://github.com/Opencomplai/opencomplai/tree/main/examples/gate-demo) exits `1` for that reason. An Article 5 result is always exit `3`. See the [exit-code matrix](../cli/exit-codes.md#high-risk-acceptance) and [`accept`](../cli/accept.md).

An acceptance acknowledges the classification. It does not state that the system is compliant.

## Names and affiliation

Product names belong to their owners. OpenComplAI is not affiliated with, endorsed by or a partner of any tool named on this page.
