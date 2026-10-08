# approve and resume

The human-in-the-loop hold. When [`check`](check.md) puts a system into
`HALTED_PENDING_REVIEW`, a person signs an approval token with `approve`, and
`resume` verifies that token and returns the system to `RUNNING`.

**What:** two commands that share one signed token. `approve` mints it, `resume`
checks it and changes the stored state.

**When:** after a `check` halted the system, which it does when the run hits a
trap (for example the Article 25 substantial-modification trap, exit `4`) or an
unresolved high-risk corroboration gap. While a system is halted,
`docs generate` refuses to produce a dossier for it and exits `4`.

**Offline:** both commands read and write local files only. The system state is
kept in `~/.opencomplai/`, or in the directory named by `OPENCOMPLAI_STATE_DIR`
when that is set.

## `approve`

Mint a signed approval token for a halted system.

=== "macOS / Linux"
    ```bash
    opencomplai approve --system-id loan-decision-model --approver alice@example.com
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai approve --system-id loan-decision-model --approver alice@example.com
    ```

| Option | Default | Description |
|---|---|---|
| `--system-id` | *(required)* | System identifier. |
| `--approver` | *(required)* | Approver identity, for example an email, bound into the token. |
| `--key` | `~/.opencomplai/signing.key` | Private signing key. Without `--key`, `SIGNING_KEY_PRIVATE` (base64 PEM) is also accepted. |
| `--role` | *(none)* | The approver's oversight role. Required when the manifest declares `human_oversight` roles, and must be one of them. |
| `--manifest` | `system-manifest.json` | Manifest whose `human_oversight` roles are checked. A missing file is fine. |
| `--output` / `-o` | `human` | `human` or `json`. |

The token is `base64(payload).signature`. The payload holds `system_id`,
`commit_ref`, `halted_at`, `approver`, `issued_at` and, when given, `role`.
`halted_at` is copied from the persisted halt record, so the token is bound to
this halt and not to any later one.

Each minted token is also appended to the signed, hash-chained oversight log
`oversight-log.json` in the state directory. Check it with
`opencomplai verify oversight-log.json --kind oversight-log`; see
[verify](verify.md).

`approve` exits `2` when the system is not `HALTED_PENDING_REVIEW`, when the
signing key is missing, when the role is missing or not declared in the
manifest, or when the oversight log cannot be written.

## `resume`

Verify a token and return a halted system to `RUNNING`.

=== "macOS / Linux"
    ```bash
    opencomplai approve --system-id loan-decision-model --approver alice@example.com -o json > approval.json
    opencomplai resume --system-id loan-decision-model --approval-token "$(jq -r .token approval.json)"

    # or keep the bare token in a file and pass it as @file
    opencomplai resume --system-id loan-decision-model --approval-token @token.txt
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai resume --system-id loan-decision-model --approval-token "@token.txt"
    ```

| Option | Default | Description |
|---|---|---|
| `--system-id` | *(required)* | System identifier. |
| `--approval-token` | *(required)* | The token, or `@path` to a file that contains it. |
| `--pub-key` | `~/.opencomplai/signing.pub` | Public key to verify the token against. |
| `--key` | `~/.opencomplai/signing.key` | Private key used only to sign the oversight log entry. With no key the entry is written unsigned and a note is printed. |
| `--output` / `-o` | `human` | `human` or `json`. |

`resume` checks the signature, that the token names this `system_id`, and that
its `halted_at` equals the persisted halt record. A token minted for an earlier
halt does not resume a later one. On success the state is saved as `RUNNING`
and a `resume_granted` entry is appended to the oversight log. Refused resumes
are not logged.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | `approve` minted a token; `resume` resumed the system, or the system was not halted and there was nothing to resume (a note is printed). |
| 2 | `approve`: not halted, signing key missing, bad role, or oversight log not writable. `resume`: token invalid, tampered or not matching the current halt (state unchanged), token file unreadable, or oversight log not writable. |

## See also

- [check](check.md): halts the system.
- [verify](verify.md): checks the `oversight-log` kind.
- [keys](keys.md): rotating the signing key that signs tokens.
