# NIST AI RMF

Opencomplai assesses `NIST_AI_RMF` (the AI Risk Management Framework 1.0, NIST AI
100-1) as a **derived** framework next to its native `EU_AI_ACT` target. Most verdicts
are **re-projected from evidence Opencomplai already gathers for the EU AI Act**, not
measured anew. Where that evidence holds nothing for a subcategory, the provider's
attestation stands in. Its status on [Frameworks](../frameworks/index.md) is "derived,
per subcategory".

## No new scanner was added

Every NIST AI RMF subcategory verdict `opencomplai gaps --target NIST_AI_RMF` prints is
either a re-statement of a rule, obligation, scan or evaluator result that
`opencomplai gaps`/`check` already compute for `EU_AI_ACT` (the same
`ArticleGapStatus` rows described in
[Control Codes → Principles → Articles](eu-ai-act-principles.md)), or a provider
attestation recorded in the manifest. Nothing inspects your system, your code or your
model any differently for NIST AI RMF than it already does for the EU AI Act.

## How the re-projection works

1. `opencomplai check`/`gaps` computes a per-EU-AI-Act-article
   `Met`/`Partial`/`Missing`/`Unverified` status from your rule engine, obligation
   catalogue, code scan and pipeline evaluator results: the ordinary `GapReport`
   (`opencomplai_core.gap_report`).
2. `data/nist_ai_rmf_subcategories.json` holds the 72 subcategories of the RMF 1.0
   core (Govern/Map/Measure/Manage, outcome text as published in NIST AI 100-1). Each
   one lists, under `eu_ai_act`, the EU AI Act articles whose evidence covers it, each
   with a mapping `confidence` (`low` or `medium`; nothing claims `high`) and a short
   note on why.
3. `opencomplai_core.nist_rmf_report.build_nist_rmf_report` walks every subcategory and:
   - looks up the `GapReport` status of each mapped article;
   - reports the **worst** status among them (the same worst-case rollup
     `principle_report.py` uses for the 6 EU Trustworthy AI principles), and
   - reports the **lowest** mapping confidence among them, never upgraded.

The mapping is per subcategory: `MAP 2.3` (data collection and selection) follows
Art. 10, while `MAP 2.1` (tasks and methods) follows Art. 11. When a mapped article
was not part of a given run's `GapReport`, the subcategory is `Unverified` with no
confidence, not a guessed verdict.

## Subcategories the EU AI Act evidence does not cover

14 subcategories have an empty `eu_ai_act` list, because nothing the tool gathers for
the EU AI Act speaks to them: GOVERN 1.7, 3.1 and 4.1; MAP 1.2, 1.3, 1.4 and 3.1;
MEASURE 2.2, 2.13, 3.2, 3.3, 4.1 and 4.2; and MANAGE 2.1. They read `Unverified` until
the provider records an attestation:

```json
{
  "compliance_targets": ["EU_AI_ACT", "NIST_AI_RMF"],
  "framework_inputs": {
    "NIST_AI_RMF": {
      "attested": {
        "NIST_AI_RMF:MANAGE 2.1": {
          "statement": "Resourcing and non-AI alternatives are reviewed each quarter.",
          "attested_by": "jane.doe@example.com",
          "attested_at": "2026-11-02"
        }
      }
    }
  }
}
```

An attested subcategory reads `Met` with confidence label `attested`; the statement is
recorded verbatim and nothing checks it. A subcategory that has EU AI Act evidence
takes no attestation: `gaps` and `check` exit `2` if you record one, because closing
the EU AI Act gap is what changes it.

## Reading a subcategory row

```text
$ opencomplai gaps --manifest system-manifest.json --target NIST_AI_RMF

Subcategory   Status    Mapping conf.   From (EU AI Act)   Rationale
GOVERN 1.2    MISSING   low             Art. 17            Re-projected via
                                                            data/nist_ai_rmf_subcategories.json
                                                            (mapping confidence=low)
                                                            from existing EU AI Act
                                                            evidence: Art. 17 -> missing
                                                            (source=obligation,
                                                            evidence=provider_qms).
```

Every re-projected row's `Rationale` names the exact EU AI Act article(s), their
gap-report status, and the evidence reference (rule id, obligation id, evaluator id or
scan finding) the verdict was derived from: the citation trail. `--output json`
carries the same fields under `nist_rmf_report.subcategories[].source_eu_ai_act_articles`
on both `opencomplai gaps --target NIST_AI_RMF` and `opencomplai check --with-gaps` (the
latter when `NIST_AI_RMF` is one of its resolved targets: `--target`, else the
manifest's `compliance_targets`, else its `compliance_target`).

## Alongside the EU AI Act

`NIST_AI_RMF` can be the only target (the manifest's `compliance_target`, or `gaps
--target NIST_AI_RMF`), which prints the subcategory table above. It can also sit next
to the EU AI Act, in the manifest's `compliance_targets` or with repeated `--target`.

Then `gaps` prints the EU AI Act table and a NIST AI RMF requirement table, and
`gaps --output json` and `check --with-gaps` also carry a NIST AI RMF framework report
(`frameworks` / `framework_reports`) next to `nist_rmf_report`. Its rows have ids
prefixed `NIST_AI_RMF:`, source `crosswalk` (or `attestation` for an attested row), and
`derived_from: "EU_AI_ACT"`. Any requirement can be excluded with a reason under
`framework_inputs.NIST_AI_RMF.excluded`. Being derived, NIST AI RMF adds no controls
and no `recommend` files. It gates `check` only if you opt in (see
[Gating other frameworks](../cli/check.md#gating-other-frameworks)).

## Honesty guarantees

- **`needs_founder_review` is always `true`.** The mapping has not been confirmed by a
  human compliance or legal reviewer.
- **Confidence never gets upgraded.** A subcategory mapped at `low` confidence is
  reported at `low`, however "measured" the underlying EU AI Act evidence is.
  `confidence_label` is always `heuristic_estimate` for a re-projected verdict, never a
  legal determination.
- **An uncovered subcategory is `Unverified`, never fabricated.** If no article maps to
  it and no attestation is recorded, or the mapped articles are not in the current run,
  the verdict says exactly that instead of guessing.
- **Links to ISO/IEC 42001 and ISO/IEC 27090 compute no verdict.** Each subcategory also
  lists related ISO/IEC 42001 rows (from NIST's own crosswalk) and ISO/IEC 27090 rows;
  see [Framework mappings](../frameworks/mappings.md). Those frameworks are assessed
  separately as the attestation-led `ISO_IEC_42001` and `ISO_IEC_27090` targets.
- **The EU AI Act `Mapped` column is a summary.** `data/framework_crosswalk.json` still
  cites one NIST category and one ISO/IEC 42001 clause per EU AI Act article in the
  default `gaps` output and the dossier. It does not decide NIST verdicts.

## A living framework

NIST AI RMF 1.0 (NIST AI 100-1, published January 2023) is the version this taxonomy
tracks. The White House's "America's AI Action Plan" (2025) directed NIST to revise
the AI RMF to remove references to misinformation, diversity/equity/inclusion, and
climate change; that revision had not been published when the taxonomy was last
checked (see `data/nist_ai_rmf_subcategories.json`'s `_meta.researched_at` and
`_meta.pending_revision_caveat`). `GOVERN 3` (workforce diversity/equity/inclusion) and
`MEASURE 2.12` (environmental impact) are the subcategories most likely to move if and
when that revision publishes. Re-verify the taxonomy against NIST's current core
tables before treating it as durable reference material.

## Where this lives in the codebase

| Concern | File |
|---|---|
| RMF 1.0 subcategories and their mapping | `packages/core/src/opencomplai_core/data/nist_ai_rmf_subcategories.json` |
| Loader | `packages/core/src/opencomplai_core/nist_ai_rmf_subcategories.py` |
| Re-projection and attestations | `packages/core/src/opencomplai_core/nist_rmf_report.py` |
| Registry entry (derived pack) | `packages/core/src/opencomplai_core/frameworks.py` |
| EU AI Act `Mapped` column summary | `packages/core/src/opencomplai_core/data/framework_crosswalk.json` |
| CLI surface | `opencomplai gaps --target NIST_AI_RMF`, `opencomplai check --with-gaps` |

See [Control Codes → Principles → Articles](eu-ai-act-principles.md) for the EU AI Act
evidence this page's verdicts are derived from, and run `opencomplai gaps --target
NIST_AI_RMF` against your own manifest to see the re-projection applied to your system.
