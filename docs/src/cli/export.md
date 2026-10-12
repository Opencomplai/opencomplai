# export

Write one neutral evidence package from a compliance artifact, as JSON or as a flat CSV, for a governance or GRC tool to read without knowing the OpenComplAI model. It reads one file and writes only the paths you give it; nothing is sent anywhere.

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai export ARTIFACT.json [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai export ARTIFACT.json [OPTIONS]
    ```

## Accepted input

A `compliance-artifact.json` written by `opencomplai check --with-gaps`. It must contain a `gap_report`; an artifact without one exits 2. The artifact can be signed or unsigned. Files written by a PowerShell or `cmd.exe` redirect are read too.

## Options

| Option | Default | Description |
|---|---|---|
| `--format` | `json` | `json` writes the package; `csv` writes one row per article. |
| `--out` | stdout | Write the package to this file (UTF-8, LF line endings) instead of stdout. |
| `--artifact-out` | none | Also write the embedded artifact to this file, so it can be given to `opencomplai verify`. |

## Package layout

The JSON package is validated by the published schema `evidence_package.schema.json` (see [published schemas](../concepts/published-schemas.md)). It contains no generation time: the same artifact always gives the same package.

| Field | Meaning |
|---|---|
| `package_version` | The package format version, `"1"`. |
| `identity.system_id` | The system the artifact was written for. |
| `identity.commit_ref` | The commit reference recorded by the check. |
| `identity.manifest_sha256` | SHA-256 of the manifest the check read; `null` when not stamped. |
| `identity.tree_sha256` | SHA-256 digest of the checked tree; `null` when the artifact does not carry one. |
| `identity.tree_dirty` | Whether the tree had uncommitted changes; `null` when the artifact does not carry it. |
| `identity.timestamp` | The time the check stamped; `null` when not stamped. |
| `provenance.cli_version` | The CLI version that wrote the artifact. |
| `provenance.rule_set_version` | The rule-set version the verdicts were computed under. |
| `provenance.schema_version` | The artifact schema version the check stamped. |
| `provenance.policy_bundle_version` | The policy bundle version, when one was used. |
| `verdict.result` | The check result, for example `pass` or `control_fail`. |
| `verdict.failed_controls` | The controls that failed in the run. |
| `verdict.pending_verifications_count` | How many verifications are still pending. |
| `articles[]` | One entry per gap-report row, in gap-report order: `article`, `status`, `source`, `evidence_ref`, `confidence` and `confidence_label`. |
| `evidence_hashes` | SHA-256 hashes of the evidence objects. |
| `verification.signed` | `true` when the embedded artifact carries a signature. |
| `verification.signature_domain` | Always `scan-status-artifact`. |
| `verification.artifact_pointer` | Always `/artifact`: where the original artifact sits in the package. |
| `verification.command` | The command that checks the embedded artifact. |
| `verification.note` | Says the public key must come from the signer and the package itself is not signed. |
| `artifact` | The original artifact, embedded unchanged. |

Fields the artifact does not carry are `null`; an older artifact still exports.

Rationale text is deliberately left out of the extracted fields and the CSV. It is still present inside the embedded `artifact`, which is the source artifact as it was written.

## CSV columns

`--format csv` writes a header row and one row per article, with LF line endings:

`system_id`, `commit_ref`, `rule_set_version`, `article`, `status`, `source`, `evidence_ref`, `confidence`, `confidence_label`

An empty cell means the value is null. A cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return gets a leading `'` so a spreadsheet does not read it as a formula.

## Verify the embedded artifact offline

The package is not signed; only the embedded artifact is. Write the artifact out, then verify it with the signer's public key:

```bash
opencomplai export compliance-artifact.json --out evidence-package.json --artifact-out embedded-artifact.json
opencomplai verify embedded-artifact.json --kind artifact --pub-key ./signing.pub
```

The key must come from the signer, never from the package. An unsigned artifact exports with `verification.signed` set to `false` and proves nothing. See [verify](verify.md).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | The package was written, whatever verdict the artifact holds. |
| 2 | The input is missing, unreadable, not an artifact or has no `gap_report`; or an output path cannot be written. |

The command moves data and never gates a pipeline. No new exit code; see [Exit codes](exit-codes.md).

## Example

```bash
opencomplai check --with-gaps --sign
opencomplai export compliance-artifact.json --format csv --out articles.csv
```
