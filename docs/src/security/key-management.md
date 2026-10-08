# Key Management

Opencomplai signs scan status artifacts with a local Ed25519 keypair. This page
covers where the keys live, how to rotate them, and how to check a signature.

The rotation cadence below is a recommendation taken from the CLI help text. It
is not a requirement of any standard. The control labels used in the code
(ISO 27001 A.8.24, FedRAMP SC-12) are mapped, not certified.

## Where keys live

| File | Contents |
|---|---|
| `~/.opencomplai/signing.key` | Private key (PEM). Created with mode `600`. |
| `~/.opencomplai/signing.pub` | Public key (PEM). Safe to share. |
| `~/.opencomplai/config.yaml` | Holds the `install_id` for this machine. |

`opencomplai init` creates the pair if there is none.

## Rotate the key

=== "macOS / Linux"
    ```bash
    opencomplai keys rotate
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai keys rotate
    ```

Rotation needs an existing `signing.key`; without one it exits 2 and tells you
to run `opencomplai init`. It then:

1. Copies the old private key to `signing.key.prev` (mode `600`) and the old
   public key to `signing.pub.prev`.
2. Writes a new `signing.key` and `signing.pub`.
3. Writes a new `install_id` into `config.yaml`.
4. Prints the new `install_id` and a 16-character SHA-256 fingerprint of the new
   public key PEM.

The recommended cadence is every 90 days.

Artifacts signed before a rotation do not verify against the new public key.
To check an old artifact, pass the archived key: `--pub-key ~/.opencomplai/signing.pub.prev`.
Only the most recent previous pair is kept; a second rotation overwrites it.

## Re-enrol in the dashboard

After a rotation, update your dashboard enrollment with the new public key. On
the dashboard side, rotating a tenant key creates a new active key, retires the
previously active ones and records a `SIGNING_KEY_ROTATED` audit event.

## Check a signature

=== "macOS / Linux"
    ```bash
    opencomplai verify compliance-artifact.json
    opencomplai verify compliance-artifact.json --pub-key ./signing.pub
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai verify compliance-artifact.json
    opencomplai verify compliance-artifact.json --pub-key .\signing.pub
    ```

The result is `verified`, `unsigned` or `invalid`. See [verify](../cli/verify.md).

## What not to commit

Never commit `signing.key`, `signing.key.prev` or any file holding the private
key. Only the public key (`signing.pub`) is meant to leave the machine. Keep
`~/.opencomplai/` out of any repository.
