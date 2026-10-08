# Regimes

Opencomplai treats the regimes it knows about in three different ways, and the difference matters more than
the name. A regime can be evaluated natively, derived from evidence gathered for another regime, or only
cited. None of these is a legal determination or a certification.

## The table

| Regime | Key | Status | How it is produced | Confidence |
|---|---|---|---|---|
| EU AI Act | `EU_AI_ACT` | Evaluated | Natively, per article, from rules, obligations, the code scan, evaluators and documentation probes. Always gates [`check`](../cli/check.md). | Per row, as the row states it. |
| NIST AI RMF 1.0 | `NIST_AI_RMF` | Derived, partial | Re-projected from the EU AI Act evidence through a crosswalk, per subcategory. No NIST scanner exists; a subcategory without a crosswalk row stays Unverified. | `low` or `medium` per crosswalk row, never raised when re-projected. Every row is flagged for review. |
| ISO/IEC 42001:2023 | `ISO_IEC_42001` | Native pack, attestation-led, partial | Native rows per clause and Annex A control. Most rows are provider attestations that read Unverified until one is recorded under `framework_inputs`; a few also look for a matching document, and the worse of the two wins. | `low`, every row flagged for review. |
| DORA | not a target | Mapped only | A citation per EU AI Act article, added by `gaps --map-to DORA`. No status is computed. | `low`, flagged for review. |
| EBA guidelines | not a target | Mapped only | The same, with `--map-to EBA`. | `low`, flagged for review. |

The wording for the first three is shared with [Frameworks](../frameworks/index.md), which is the page to
read for targeting, exclusions, attestations and gating. `EU_AI_ACT`, `NIST_AI_RMF` and `ISO_IEC_42001` are
the only keys `--target` and `compliance_targets` accept; any other key, DORA and EBA included, exits `2`.
The `ComplianceTarget` value that the dossier schema embeds is unchanged by the mapped-only regimes.

## Evaluated

The EU AI Act is the one regime with a deterministic verdict per article. Its report is always computed,
because the derived regimes are built from its evidence. See [Rules](rules.md),
[Evidence](evidence.md) and [Evaluators](evaluators.md).

## Derived

NIST AI RMF re-states what the EU AI Act evidence already shows. It adds no scanner, evaluator or probe, and
a gate on it fails on the same underlying gaps. See [NIST AI RMF](nist-ai-rmf.md).

## Native, attestation-led

ISO/IEC 42001 rows are mostly statements by you that a clause is met. The tool records an attestation
verbatim and does not check it; the row then reads Met with the source `attestation` and the confidence
label `attested`. Nothing here certifies ISO/IEC 42001 conformity. Clause titles come from the project's
draft catalogue, not from the licensed standard text.

## Mapped only

A mapped-only regime is a pointer from an EU AI Act article to the part of another text that covers similar
subject matter. It has no verdict, no probe, no control and no exit code, and the output without
`--map-to` is byte-identical to before. The identifiers were written from general knowledge and are not
checked against the primary texts. The rows and the exact review flags are on
[Mapped-only regimes](mapped-regimes.md); they are not repeated here.

## Where the data lives

Each regime keeps its data in its own file, with `source`, `confidence` and `needs_founder_review` on every
entry. The mapped-only citations are kept apart from the NIST and ISO crosswalk, so adding a citation never
changes the data version of a framework that produces verdicts. See
[Rule-set versioning](rule-set-versioning.md) for what a data version is.
