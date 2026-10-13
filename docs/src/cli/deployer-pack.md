# deployer-pack

Seal an instructions-for-use document into one portable file, named after its
own SHA-256, that a recipient can check offline. The group does three jobs:
`build` seals a pack, [`verify`](verify.md) checks one, and `import` records a
provider's pack in your own manifest as upstream evidence.

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

## `deployer-pack import`

Record that you received a provider's pack and checked it. The pack is verified
first, exactly as `verify --kind deployer-pack` does, and an invalid pack is
refused before anything is written.

=== "macOS / Linux"
    ```bash
    opencomplai deployer-pack import provider/deployer_pack_0123456789ab.json \
      --manifest system-manifest.json --pub-key provider.pub
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai deployer-pack import provider\deployer_pack_0123456789ab.json --manifest system-manifest.json --pub-key provider.pub
    ```

| Option | Default | Description |
|---|---|---|
| `pack` | *(required)* | The provider's `deployer_pack_<id>.json`. One explicit path; nothing is globbed. |
| `--manifest` / `-m` | `system-manifest.json` | Your system manifest. It must already exist and be valid; it is never created. |
| `--pub-key` | `~/.opencomplai/signing.pub` | The provider's public key, needed only for a signed pack. Same meaning as in `verify`. |
| `--output` / `-o` | `human` | `human` or `json`. |

The record is added to the manifest's `imported_evidence` map under the key
`deployer_pack:<first 12 hex of the pack SHA-256>`, and holds:

- the pack id and the full `pack_sha256` (the bundle hash);
- the provider's system id, as the pack states it;
- `verification`: `verified` or `unsigned`;
- the signer key id, when `verification` is `verified`;
- the import date and the basename of the pack file.

Every other manifest key is kept as it was. Importing the same pack again changes
nothing and keeps the first import date; the same pack imported again with a
different verification outcome (for example unsigned, then verified with a key)
replaces the record.

- **The record is provenance, not a verdict.** It says you received a pack and
  what the check found at that time. It never makes an article Met.
- **`verified`** means the hash and signature match the public key you supplied.
  It says nothing about who holds that key.
- **`unsigned`** means only the hash was checked. No signature was checked.
- **`gaps` and `check` read the record for Art. 26 only**, and only when a
  recorded checker session makes Art. 26 apply to you as a deployer of a
  high-risk system. A missing Art. 26 row then reads Partial at most, with the
  reason "provider-supplied, not verified by the deployer". It is never Met, and
  `verified` and `unsigned` read the same. The pack is the provider's statement,
  not evidence about your deployment. An expired agent mandate still reads
  Missing. The record stays in your local manifest and is not pushed.

`--output json` prints one object with `pack_id`, `pack_sha256`,
`provider_system_id`, `verification`, `signer_key_id`, `manifest` and `recorded`
(`false` when the pack was already imported).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | `build`: the pack was written. `import`: the pack was recorded or was already imported (an unsigned pack is recorded). |
| 2 | `build`: the instructions file is unreadable or is not an instructions-for-use document, no system id is available, `--issued-on` is malformed, or `--sign` has no key. `import`: the pack is invalid, tampered or unreadable, the public key is wrong or missing, or the manifest is missing or invalid. Nothing is written. |

For the exit codes of the `verify` step see [verify](verify.md#exit-codes).

## See also

- [instructions generate](instructions-generate.md): writes the file a pack wraps.
- [verify](verify.md): checks a pack.
