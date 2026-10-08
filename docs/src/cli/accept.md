# accept

Record, in the repository, that a person has accepted a system's high-risk
classification. The record is a signed JSON file you commit to git. `check`
reads it from the repository (never from your home directory), so it works on
a fresh CI runner.

This page describes what the command does and what `check` does with the
file. It makes no claim about the legal effect of an acceptance; the
statement is free text that you write.

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai accept --accepted-by <who> --statement <text> [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai accept --accepted-by <who> --statement <text> [OPTIONS]
    ```

## Options

| Option | Default | Description |
|---|---|---|
| `--manifest` / `-m` | `system-manifest.json` | System manifest the record is bound to. |
| `--accepted-by` | *(required)* | Who is accepting (name or email). Must not be empty. |
| `--statement` | *(required)* | Free-text statement in your own words. Must not be empty. |
| `--repo-root` | `.` | Repository root. The record is written under `.opencomplai/acceptances/`. |
| `--trap-approval` | off | Write a trap-approval record instead of a classification acceptance. Needs `--change-context`. `check` honours it, alongside a valid acceptance, for that change context only. |
| `--change-context` | *(none)* | The change being approved. Only with `--trap-approval`. |
| `--key` | `~/.opencomplai/signing.key` | Private signing key. `SIGNING_KEY_PRIVATE` (base64 PEM), when set, takes precedence. |
| `--output` / `-o` | `human` | `human` or `json`. JSON prints `path`, `record_type`, `key_id` and `manifest_fingerprint`. |

## What it writes

`.opencomplai/acceptances/<system_id>.classification_acceptance.json` (or
`.trap_approval.json`). Commit it. There is one active record per system and
type; running `accept` again replaces the file and git history keeps the old
one.

| Field | Meaning |
|---|---|
| `schema_version` | `1`. |
| `record_type` | `classification_acceptance` or `trap_approval`. |
| `system_id` | The manifest's `system_id`. |
| `manifest_fingerprint` | Fingerprint of the manifest's watched fields (intended purpose, model architecture, high-risk presumption, training data description, operator roles, human oversight). |
| `accepted_by`, `statement` | What you typed. |
| `accepted_at` | UTC time of the command, `YYYY-MM-DDTHH:MM:SSZ`. |
| `change_context` | Trap approvals only. |
| `public_key`, `key_id` | The signer's public key and its `sha256:` id. |
| `signature` | Ed25519 signature over every other field, under its own signing domain. |

## What `check` does with it

A valid record stops `EU_AIA_ART6_HIGH_RISK` counting as a failure, but any
Missing EU row still fails the check (see
[exit codes](exit-codes.md#high-risk-acceptance)). Art. 5 (exit `3`),
validation failures and every other failed control still fail it. A trap is
still exit `4` unless a valid trap approval for the same change context sits
alongside a valid acceptance. If the record exists but is
not valid, `check` prints a warning naming the state (`stale`, `unsigned`,
`tampered`, `untrusted`, `mismatch` or `malformed`) and the classification
still fails.

Editing a watched manifest field (for example the intended purpose) makes the
record `stale`; run `accept` again after reviewing the change.

## Who signed it

The record carries its own public key, so anyone can check that it was not
altered after signing. That does not prove who the signer is. Authority comes
from git: who may merge the file (for example through CODEOWNERS). To pin the
signers you trust, set `OPENCOMPLAI_TRUSTED_KEY_IDS` to a comma-separated list
of `key_id` values; a record signed by any other key is `untrusted`.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Record written. |
| `2` | Invalid input, missing or invalid manifest, no signing key, or a prohibited (Art. 5) system. Nothing is written. |

An acceptance can never apply to a prohibited practice, so `accept` refuses
those systems.
