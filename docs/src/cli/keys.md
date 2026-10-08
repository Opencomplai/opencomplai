# keys

Signing key management for the local Ed25519 keypair that signs artifacts,
dossiers and approval tokens.

Today the group has one subcommand, `keys rotate`. For where the keys live and
how to verify a signature, see [Key management](../security/key-management.md).

## `keys rotate`

Generate a new keypair, archive the old one and print the new public key
fingerprint.

=== "macOS / Linux"
    ```bash
    opencomplai keys rotate
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai keys rotate
    ```

| Option | Default | Description |
|---|---|---|
| `--output` / `-o` | `human` | `human` or `json`. |

What it does:

1. Copies `~/.opencomplai/signing.key` to `signing.key.prev` (mode `0600`) and
   `signing.pub` to `signing.pub.prev`. Only the most recent previous pair is
   kept; a second rotation overwrites it.
2. Writes a new `signing.key` and `signing.pub`.
3. Stores the new `install_id` in the local config.
4. Prints the new `install_id`, the public key fingerprint (`sha256:` and the
   first 16 hex characters of the SHA-256 of the public key file) and the path
   of the archived private key.

With `--output json` the same facts are one object with `status`
(`rotated`), `new_install_id`, `public_key_fingerprint` and `archived_to`.

The recommended cadence is every 90 days.

## What to do afterwards

- Artifacts signed before the rotation do not verify against the new public
  key. Keep `signing.pub.prev` if you need to verify older files, and pass it
  as the public key to [`verify`](verify.md).
- If this install is enrolled in the dashboard, update the enrolment with the
  new public key; see [dashboard](dashboard.md).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Rotated. |
| 1 | The `cryptography` package is not installed. |
| 2 | No signing key exists yet. Run [`init`](init.md) first. |
