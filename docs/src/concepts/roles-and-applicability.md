# Roles and applicability

An AI system can sit under more than one role in the EU AI Act (a provider that also deploys it, for
example), and an article that only binds one of those roles is not a gap for a system that is not in it.
Opencomplai records the roles and can move such an article out of the gap table, but only from a recorded
applicability checker session.

## Roles in the manifest

| Field | Meaning |
|---|---|
| `operator_role` | The primary role. Always written when a role is known. |
| `operator_roles` | Every role the checker found, as a list. Omitted when empty. |
| `checker_session` | A reference to the checker run, including the `obligation_ids` it recorded. |

Both role fields are watched by the control fingerprint, so a role change re-queues the controls it
affects. An empty `operator_roles` is skipped when the fingerprint is computed, so manifests written before
the field existed keep their old fingerprint.

[`opencomplai checker`](../cli/checker.md) takes `--entity-type` once per role. The checker runs once per
role and the obligations are merged. `--write-manifest` appends to an existing manifest instead of
overwriting it. Without `--entity-type`, no `operator_roles` is written.

## Applicability in the gap report

Each EU AI Act article in the gap article map can carry `applies_when_any`: a list of checker obligation
ids. When a recorded session has obligation ids and none of the listed ones is among them, the article:

- leaves `GapReport.articles`, so it has no row, no probe and no control;
- appears in `GapReport.not_applicable`, a map from the article to the reason.

`not_applicable` is omitted from the JSON when it is empty, and no new `GapStatus` value exists: an article
is either a row with a status or it is in `not_applicable`. The reason text names the obligation and the
session and has no date. [`check`](../cli/check.md) with `--with-gaps` prints a one-line count of articles
that are not applicable to the session; `gaps --output json` carries the map.

Only obligation ids decide. Roles are named in the reason text and are never used to decide.

## Without a session

With no checker session, or a session with no recorded obligation ids (a legacy session), nothing moves.
The output is byte-identical to a run that never heard of applicability. That is deliberate: applicability
is evidence you recorded, not something the tool infers.

!!! note "Needs founder review"
    Each `applies_when_any` entry carries an `applicability_note` with `confidence: low` and
    `needs_founder_review: true`. The article-to-obligation reading is an operator-role mapping, not a legal
    determination.

## Why `framework_inputs.EU_AI_ACT` stays rejected

The manifest's `framework_inputs` can exclude requirements of other frameworks (see
[Frameworks](../frameworks/index.md)). It cannot name `EU_AI_ACT`: `gaps` and `check` exit `2`. A declared
exclusion is a statement you typed; applicability is derived from a recorded checker session. Letting the
first stand in for the second would let a manifest edit remove an obligation without the checker ever
saying it did not apply, so the two stay separate.
