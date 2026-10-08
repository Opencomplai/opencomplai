# High-risk acceptance

A system that classifies as high-risk fails `check` with exit `1` until someone records that they have seen
that classification. This page describes the mechanism: a signed record in the repository, bound to the
manifest. It makes no statement about what an acceptance means in law; the statement in the record is free
text the signer writes.

## The record

[`opencomplai accept`](../cli/accept.md) writes one JSON file under `.opencomplai/acceptances/`, named for
the system and the record type, and you commit it. Two record types exist: `classification_acceptance` and
`trap_approval`. There is one active record per system and type; running `accept` again replaces the file
and git history keeps the old one.

| Field | Role |
|---|---|
| `manifest_fingerprint` | Ties the record to the manifest it was written for. |
| `accepted_by`, `statement` | What the signer typed. Neither may be empty. |
| `accepted_at` | UTC time of the command. |
| `public_key`, `key_id` | The signer's public key and its `sha256:` id. |
| `signature` | Ed25519 over every other field, under its own signing domain. |

`check` reads the record from the repository and never from your home directory, so it works on a fresh CI
runner.

## Bound to the manifest

The fingerprint covers the manifest's watched fields: intended purpose, model architecture, high-risk
presumption, training data description, operator roles and human oversight. Edit one of them and the record
is `stale`; the classification fails again until someone reviews the change and runs `accept` again.

## What it changes

A valid record stops `EU_AIA_ART6_HIGH_RISK` counting as a failed control. That is all it removes.

- Any EU AI Act row that is `missing` still fails the check, and its article id is listed instead.
- With a valid record and no missing rows, `check` exits `0`.
- A trap approval is honoured only together with a valid acceptance, and only for the same change context.

## What it never changes

| Case | Result |
|---|---|
| Article 5 (prohibited practice) | Exit `3`, whatever the record. `accept` refuses a prohibited system. |
| Article 25 trap | Exit `4` and the halt, unless a valid trap approval for the same change context sits alongside a valid acceptance. An approval alone is not honoured. |
| Validation failures and every other failed control | Unchanged. |
| A record that is stale, unsigned, tampered, untrusted, mismatched or malformed | The classification still fails, with a warning naming the state. |

The full table is in [Exit codes](../cli/exit-codes.md#high-risk-acceptance).

## Who signed it

The record carries its own public key, so anyone can check it was not altered after signing. That does not
show who the signer is. Authority comes from git: who may merge the file, for example through CODEOWNERS.
To pin the signers you trust, set `OPENCOMPLAI_TRUSTED_KEY_IDS` to a comma-separated list of `key_id`
values; a record signed by any other key is `untrusted`.

!!! note "Mechanism only"
    An acceptance acknowledges the Art. 6 classification. It does not state that the system is compliant
    and it removes no other obligation. The record's metadata is flagged `confidence: medium` and
    `needs_founder_review: true` in its source.
