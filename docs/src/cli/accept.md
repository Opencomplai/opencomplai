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
| `--statement` | *(required, unless `--proposal`)* | Free-text statement in your own words. Must not be empty. With `--proposal` it defaults to `Confirmed the proposed classification: <area>`. |
| `--repo-root` | `.` | Repository root. The record is written under `.opencomplai/acceptances/`. |
| `--trap-approval` | off | Write a trap-approval record instead of a classification acceptance. Needs `--change-context`. `check` honours it, alongside a valid acceptance, for that change context only. |
| `--change-context` | *(none)* | The change being approved. Only with `--trap-approval`. |
| `--exemption` | off | Write an `art_6_3_exemption` record: a declaration of the Art. 6(3) grounds you relied on. Cannot be combined with `--trap-approval`. |
| `--ground` | the manifest's `checker_session.derogation_grounds` | An Art. 6(3) ground, repeatable: `hr3_art_6_3`, `hr4_narrow_task`, `hr5_no_significant_risk` or `hr6_accessory`. Only with `--exemption`; exit `2` when none is given and the manifest has none. |
| `--proposal` | *(none)* | Confirm a `classification-proposal.json` written by [`scan --propose`](scan.md#suggesting-a-classification-propose). Cannot be combined with `--trap-approval`, `--exemption` or `--change-context`. |
| `--yes` / `-y` | off | Confirm without the prompt. Only with `--proposal`; otherwise exit `2`. |
| `--key` | `~/.opencomplai/signing.key` | Private signing key. `SIGNING_KEY_PRIVATE` (base64 PEM), when set, takes precedence. |
| `--output` / `-o` | `human` | `human` or `json`. JSON prints `path`, `record_type`, `key_id` and `manifest_fingerprint`, plus `grounds` for an exemption, or `proposal_sha256` and `confirmed_area` for a proposal confirmation. |

## What it writes

`.opencomplai/acceptances/<system_id>.classification_acceptance.json` (or
`.trap_approval.json`, `.art_6_3_exemption.json` or
`.classification_proposal_confirmation.json`). Commit it. There is one active record per system and
type; running `accept` again replaces the file and git history keeps the old
one.

| Field | Meaning |
|---|---|
| `schema_version` | `1`. |
| `record_type` | `classification_acceptance`, `trap_approval`, `art_6_3_exemption` or `classification_proposal_confirmation`. |
| `system_id` | The manifest's `system_id`. |
| `manifest_fingerprint` | Fingerprint of the manifest's watched fields (intended purpose, model architecture, high-risk presumption, training data description, operator roles, human oversight). |
| `accepted_by`, `statement` | What you typed. |
| `accepted_at` | UTC time of the command, `YYYY-MM-DDTHH:MM:SSZ`. |
| `change_context` | Trap approvals only. |
| `grounds` | Exemptions only: the Art. 6(3) ground ids you declared, in a fixed order. |
| `needs_legal_review` | Exemptions only: always `true`, inside the signed bytes. |
| `proposal_sha256` | Proposal confirmations only: the `sha256:` digest of the proposal file as it was shown to you. |
| `confirmed_area` | Proposal confirmations only: the proposal's `area`, as shown. |
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

An exemption record is declared by a person. It is not a legal finding that
the exemption applies, and `check` does not read it yet.

## Confirming a classification proposal

[`scan --propose`](scan.md#suggesting-a-classification-propose) suggests a
classification from your code; you confirm it. `accept --proposal` is the
confirmation step:

=== "macOS / Linux"
    ```bash
    opencomplai accept --accepted-by <who> --proposal classification-proposal.json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai accept --accepted-by <who> --proposal classification-proposal.json
    ```

The proposal file holds the suggested area (or `none`), a confidence label, the
supporting and minority evidence with file and line, any prohibited-practice
signals, the digest of the scan inputs, the manifest fingerprint it was written
for, and its own `proposal_sha256`. The command checks that digest and the
manifest fingerprint, prints a summary, and asks `Confirm this classification
proposal?`. Only a yes writes
`.opencomplai/acceptances/<system_id>.classification_proposal_confirmation.json`,
a signed record that carries the proposal's digest and area. Commit it together
with the proposal file.

- **Not confirmed is exit `1`.** Answering no, or having no terminal to answer on
  without `--yes`, prints "Not confirmed; nothing written." and exits `1`.
- **Edits are detected.** Editing the proposal before confirming exits `2` (its
  digest no longer matches). Editing it after confirming makes the confirmation
  `proposal_changed`.
- **The manifest must be the one the proposal was written for.** If it changed,
  the command exits `2`; run `scan --propose` again.
- **It states only that a person confirmed the proposal as shown.** The record is
  not a legal classification, and your declared purpose stays the source.
- **`check --scan` reads a confirmed proposal.** It adds a `confirmed_proposal:<area>`
  row when the proposal names an Annex III area your declared purpose does not cover
  (see [`check`](check.md)). The confirmation is not a classification acceptance: it does
  not change the Art. 6 result that `accept` writes without `--proposal`. An edited or
  stale proposal is ignored.

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
| `1` | With `--proposal`: the proposal was not confirmed. Nothing is written. |
| `2` | Invalid input, missing or invalid manifest, no signing key, an edited or stale proposal, or a prohibited (Art. 5) system. Nothing is written. |

An acceptance can never apply to a prohibited practice, so `accept` refuses
those systems.
