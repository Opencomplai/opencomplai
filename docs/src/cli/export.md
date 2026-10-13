# export

Write one neutral evidence package from a compliance artifact, as JSON or as a flat CSV, for a governance or GRC tool to read without knowing the OpenComplAI model. It reads one file (with `--sign` it also reads your signing key) and writes only the paths you give it; nothing is sent anywhere.

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

A `compliance-artifact.json` written by `opencomplai check`. `--with-gaps` is not needed: an artifact without a `gap_report` exports with `gaps_included` set to `false` and an empty `articles` list. The artifact can be signed or unsigned. Files written by a PowerShell or `cmd.exe` redirect are read too.

## Options

| Option | Default | Description |
|---|---|---|
| `--format` | `json` | `json` writes the package; `csv` writes one row per article. |
| `--out` | stdout | Write the package to this file (UTF-8, LF line endings) instead of stdout. |
| `--artifact-out` | none | Also write the embedded artifact to this file, so it can be given to `opencomplai verify`. |
| `--sign` | off | Sign the whole JSON package. Refused with `--format csv`. See [Signed package](#signed-package). |
| `--key` | `~/.opencomplai/signing.key` | Private key PEM used by `--sign`. `SIGNING_KEY_PRIVATE` takes precedence when it is set. |

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
| `gaps_included` | `false` when the artifact had no gap report and `articles` is empty; the key is absent when gaps are included. |
| `evidence_hashes` | SHA-256 hashes of the evidence objects. |
| `verification.signed` | `true` when the embedded artifact carries a signature. |
| `verification.signature_domain` | Always `scan-status-artifact`. |
| `verification.artifact_pointer` | Always `/artifact`: where the original artifact sits in the package. |
| `verification.command` | The command that checks the embedded artifact. |
| `verification.note` | Says the public key must come from the signer, and whether the package itself is signed (only with `--sign`) or only the embedded artifact is. |
| `artifact` | The original artifact, embedded unchanged. |
| `package_signature` | The package signature: `algorithm`, `domain`, `signer_key_id`, `signature` and `command`. Present only on a package exported with `--sign`; the key is absent otherwise. |

Fields the artifact does not carry are `null`; an older artifact still exports.

Rationale text is deliberately left out of the extracted fields and the CSV. It is still present inside the embedded `artifact`, which is the source artifact as it was written.

## CSV columns

`--format csv` writes a header row and one row per article, with LF line endings:

`system_id`, `commit_ref`, `rule_set_version`, `article`, `status`, `source`, `evidence_ref`, `confidence`, `confidence_label`, `tree_sha256`, `tree_dirty`, `signed`, `verdict`

The last four columns repeat the same package-level value on every row. `tree_sha256` and `tree_dirty` come from the identity block; `signed` is `true` or `false` and `verdict` is the check result. Booleans are written as `true` or `false`. The `signed` column means the embedded artifact carries a signature; it does not mean the CSV is signed, and a CSV never carries a signature.

An empty cell means the value is null. A cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return gets a leading `'` so a spreadsheet does not read it as a formula.

## Signed package

The package is signed only with `--sign`. An unsigned package is exactly as before: it has no `package_signature` key and its bytes do not change.

```bash
opencomplai export compliance-artifact.json --sign --out evidence-package.json
opencomplai verify evidence-package.json --kind evidence-package --pub-key ./signing.pub
```

- **What is signed:** every value of the package except `package_signature` itself, under its own signing domain, `evidence-package`. A signature made for the artifact or for another kind of file does not verify here. Changing any value, including the embedded artifact or the signature, makes `verify` report `invalid`.
- **Which key:** the one from `--key`, or `SIGNING_KEY_PRIVATE` when it is set. `package_signature.signer_key_id` names the signer's key; `verify` checks it against the public key you pass. The public key must come from the signer, never from the package.
- **What it does not cover:** whitespace between JSON tokens is not a value and is not signed. A byte change that breaks the JSON is bad input (exit 2), not `invalid`.
- **CSV:** `--sign` is refused with `--format csv` (exit 2); the CSV carries no signature.
- **Compatibility:** a reader that validates packages with the older, closed schema rejects the new `package_signature` key. That is why signing is opt-in.

`--sign` needs a signing key. Without one it exits 2 and writes nothing; run `opencomplai init` or set `SIGNING_KEY_PRIVATE`.

The embedded artifact is still verified separately, as shown next.

## Verify the embedded artifact offline

The embedded artifact carries its own signature, whether or not the package is signed. Write the artifact out, then verify it with the signer's public key:

```bash
opencomplai export compliance-artifact.json --out evidence-package.json --artifact-out embedded-artifact.json
opencomplai verify embedded-artifact.json --kind artifact --pub-key ./signing.pub
```

The key must come from the signer, never from the package. An unsigned artifact exports with `verification.signed` set to `false` and proves nothing. See [verify](verify.md).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | The package was written, whatever verdict the artifact holds. |
| 2 | The input is missing, unreadable or not an artifact; `--sign` is used with `--format csv` or without a signing key; or an output path cannot be written. |

The command moves data and never gates a pipeline. No new exit code; see [Exit codes](exit-codes.md).

## Example

```bash
opencomplai check --with-gaps --sign
opencomplai export compliance-artifact.json --format csv --out articles.csv
```
