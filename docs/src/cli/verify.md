# verify

Check that a signed file is intact. One command, dispatched by kind; the kinds
are listed in the [Kinds](#kinds) table. The default is `artifact` (the
`compliance-artifact.json` written by `check`).

`verify` only reads. It never signs and never writes or modifies a file.

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai verify <path> [--kind artifact] [--pub-key <pem>] [--output human|json]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai verify <path> [--kind artifact] [--pub-key <pem>] [--output human|json]
    ```

## Options

| Option | Default | Description |
|---|---|---|
| `path` | *(required)* | File to verify. |
| `--kind` | `artifact` | What kind of file this is. See [Kinds](#kinds). |
| `--pub-key` | `~/.opencomplai/signing.pub` | Public key (PEM) to verify against. |
| `--output`, `-o` | `human` | `human` or `json`. |
| `--expect` | *(none)* | `KEY=VALUE` extra check, repeatable, each key once. See [Expect keys](#expect-keys). |

## Kinds

| Kind | File |
|---|---|
| `artifact` | Scan status artifact (`compliance-artifact.json`). |
| `dossier` | Annex IV dossier (`dossier_<id>.json`), written by `docs generate`. |
| `oversight-log` | Oversight log (`oversight-log.json` in the state directory), appended by `approve` and `resume`. |
| `incident-log` | Incident log (`incident-log.json`, beside the register), appended by the `incident` commands. |
| `agent-log` | Agent decision log (`agent-log.jsonl` by default); `agents verify-log` checks the same file. |
| `agent-attestation` | Agent mandate attestation (`agent-attestation-<agent_id>.json`), written by `agents attest`. |
| `deployer-pack` | Deployer pack (`deployer_pack_<hash>.json`), written by `deployer-pack build`. |

## Expect keys

| Kind | Keys |
|---|---|
| `agent-attestation` | `now=<ISO UTC>`, `mandate_sha256=sha256:...` |
| `oversight-log`, `incident-log`, `agent-log` | `head=<hash>`, `count=<n>` |
| every other kind | none; any `--expect` exits 2 |

A log command prints `head=... count=...` on its last line. Keep that line
somewhere the log's writer cannot edit, and pass it back with
`--expect head=<hash> --expect count=<n>` to detect removed entries. Without an
anchor a chain cannot show that the newest entries were removed. A log with no
entries is `invalid`, never `verified`.

## Example output

A good signature:

```text
verified: signature matches
```

No signature in the file (for example, it was written by `check` without a key):

```text
unsigned: no signature present
```

A changed file, or the wrong key:

```text
INVALID: signature does not match
```

With `--output json` the same result is one object:

```json
{"kind": "artifact", "status": "unsigned", "detail": "no signature present"}
```

`status` is `verified`, `unsigned` or `invalid`. An unsigned file is reported
as `unsigned`, never as `invalid`: nothing was tampered with, nothing was signed.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | `verified`. |
| 1 | `unsigned` or `invalid`. Use `status` in the JSON output to tell them apart. A log with no entries is `invalid`. |
| 2 | Bad input: file missing or unreadable, not valid JSON or schema, unknown `--kind` (the message lists the registered kinds), the public key file is missing, an `--expect` key the kind does not support, a repeated `--expect` key, or a `count` that is not a whole number. |

An unsigned file reports `unsigned` even when no public key file exists, because
the key is only read once there is a signature to check.

See also [Key management](../security/key-management.md).
