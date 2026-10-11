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

The files you can hand over are listed in [Feed your governance platform](#feed-your-governance-platform). `opencomplai push` uploads to the OpenComplAI dashboard only when you run it.

## Feed your governance platform

These are files you hand over; nothing is sent to a platform by this tool, no connector exists and no platform is a partner of OpenComplAI.

**What to hand over**

| Output | File or flag | How to produce it | Use it for |
|---|---|---|---|
| Signed artifact | `compliance-artifact.json` | `opencomplai check --sign` (or `--sign-if-available`) | The verdict, checkable offline with the public key |
| Gap report JSON | `opencomplai gaps --output json`, or `gap_report` inside the artifact | `opencomplai gaps --output json`; or `opencomplai check --with-gaps` to embed it as `gap_report` in the artifact | Per-article status for a reviewer |
| SARIF 2.1.0 | `--sarif-output` | `opencomplai check --sarif-output check.sarif` (verdict); `opencomplai scan --sarif-output` (scan evidence) | Reading the verdict or the scan evidence as SARIF |
| JUnit XML | `--report-junit` | `opencomplai check --report-junit report.xml` | A CI test report; a failure for `control_fail`, `trap_detected`, `policy_block` or `validation_fail` |
| Annex IV dossier | `dossier_<id>.json` | `opencomplai docs generate`, then `opencomplai verify dossier_<id>.json --kind dossier` | The technical documentation draft, with honest placeholders |

### Verify the signature offline

The recipient needs only the artifact and the public key (`signing.pub`), never the private key. Verification runs offline:

```bash
opencomplai verify compliance-artifact.json
opencomplai verify compliance-artifact.json --pub-key ./signing.pub
```

| Exit code | Result |
|---|---|
| `0` | Verified: the signature matches the artifact. |
| `1` | Unsigned or invalid. |
| `2` | Bad input: the file or the key cannot be used. |

An unsigned artifact reports `unsigned` and proves nothing. See [verify](../cli/verify.md) and [key management](../security/key-management.md).

### What the fields mean

Artifact fields:

| Field | Meaning |
|---|---|
| `result` | The verdict: `pass`, `control_fail`, `validation_fail`, `policy_block`, `trap_detected` or `degraded_complete`. |
| `failed_controls` | The controls that failed in this run. |
| `evidence_hashes` | SHA-256 hashes of the evidence objects. |
| `rationale_hash` | SHA-256 of the assessment rationale. |
| `signature` | Base64 signature; `null` when the artifact is unsigned. |
| `gap_report` | The per-article gap status; present only with `--with-gaps`. |
| `manifest_sha256`, `timestamp`, `rule_set_version`, `cli_version`, `schema_version` | Provenance stamps written by the check. |

Gap row fields (one row per article in `articles[]`):

| Field | Meaning |
|---|---|
| `article` | The EU AI Act article reference, for example `Art. 6`. |
| `status` | `met`, `partial`, `missing` or `unverified`. |
| `source` | Where the status comes from. |
| `evidence_ref` | The rule id, obligation id, evaluator id or scan finding the row points to. |
| `rationale` | The reason recorded for the status. |
| `confidence` | A heuristic confidence from 0 to 1; `null` when not assessed. |
| `confidence_label` | The label that marks the confidence as a heuristic estimate. |

The gap report envelope printed by `opencomplai gaps --output json` is not signed. A `met` or `partial` row is an automated heuristic, not a legal finding. See [published schemas](../concepts/published-schemas.md) and [gaps](../cli/gaps.md).

A flat system-by-article CSV is not produced by the CLI in this release.

## When an accepted high-risk system exits 0

Accepting a classification does not make `opencomplai check` pass by itself. After `opencomplai accept` records it, the Art. 6 high-risk row no longer fails the check, but every other EU AI Act row still counts: `check` exits `0` only when no other EU AI Act row is Missing, and exits `1` with the Missing ids otherwise. The accepted system in the [gate demo](https://github.com/Opencomplai/opencomplai/tree/main/examples/gate-demo) exits `1` for that reason. An Article 5 result is always exit `3`. See the [exit-code matrix](../cli/exit-codes.md#high-risk-acceptance) and [`accept`](../cli/accept.md).

An acceptance acknowledges the classification. It does not state that the system is compliant.

## Names and affiliation

Product names belong to their owners. OpenComplAI is not affiliated with, endorsed by or a partner of any tool named on this page.
