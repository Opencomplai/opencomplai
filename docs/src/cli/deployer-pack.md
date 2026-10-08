# deployer-pack

Seal an instructions-for-use document into one portable file, named after its
own SHA-256, that a recipient can check offline.

**What:** `deployer-pack build` wraps the JSON written by
[`instructions generate`](instructions-generate.md) with a count of how many
items it provides and an integrity block (its SHA-256 and, when asked, an
Ed25519 signature).

**Offline and metadata-only:** a pack is generated on your machine and is never
uploaded. Only its hash and counts are recorded in an artifact's
`summaries.packs`. The same inputs on the same day give byte-identical output.

This page describes the file and the command. It makes no statement about
whether a pack satisfies any Article of the EU AI Act.

## `deployer-pack build`

=== "macOS / Linux"
    ```bash
    opencomplai instructions generate --manifest system-manifest.json
    opencomplai deployer-pack build \
      --instructions ./instructions-for-use/instructions_for_use.json \
      --sign
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai instructions generate --manifest system-manifest.json
    opencomplai deployer-pack build --instructions .\instructions-for-use\instructions_for_use.json --sign
    ```

| Option | Default | Description |
|---|---|---|
| `--instructions` | *(required)* | `instructions_for_use.json` written by `opencomplai instructions generate`. |
| `--system-id` | from the file | System identifier. Required only when the instructions file has none. |
| `--output-dir` | `./deployer-pack` | Directory for the pack. Created if missing. |
| `--sign` / `--no-sign` | `--no-sign` | Sign the pack with the signing key. Exits `2` before writing anything when no key is available. |
| `--issued-on` | today | Issue date, `YYYY-MM-DD`. |
| `--output` / `-o` | `human` | `human` or `json`. |

The key is `~/.opencomplai/signing.key` or, when set, `SIGNING_KEY_PRIVATE`
(base64 PEM). Without `--sign` the pack is written unsigned and says so.

## Output

One file, `deployer_pack_<first 12 hex of the pack SHA-256>.json`, in
`--output-dir`. Human output prints the path, the full `pack_sha256`, whether the
pack is signed, and how many items were provided.

`--output json` prints one object:

```json
{
  "pack_sha256": "...",
  "path": "deployer-pack/deployer_pack_0123456789ab.json",
  "signed": true,
  "items_provided": 8,
  "items_not_captured": 2
}
```

The public key is never embedded in the pack. A verifier supplies it.

## Verifying a pack

Verification is the `deployer-pack` kind of [`verify`](verify.md).

=== "macOS / Linux"
    ```bash
    opencomplai verify deployer-pack/deployer_pack_0123456789ab.json \
      --kind deployer-pack --pub-key signing.pub
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai verify deployer-pack\deployer_pack_0123456789ab.json --kind deployer-pack --pub-key signing.pub
    ```

The hash is checked first. A pack with no signature reports `unsigned` when the
hash matches; a changed file, a wrong key or a missing key for a signed pack
reports `invalid`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | `build`: the pack was written. |
| 2 | `build`: the instructions file is unreadable or is not an instructions-for-use document, no system id is available, `--issued-on` is malformed, or `--sign` has no key. |

For the exit codes of the `verify` step see [verify](verify.md#exit-codes).

## See also

- [instructions generate](instructions-generate.md): writes the file a pack wraps.
- [verify](verify.md): checks a pack.
