# NIST AI RMF

Opencomplai evaluates `NIST_AI_RMF` (the AI Risk Management Framework 1.0, NIST AI
100-1) as a second compliance target alongside its native `EU_AI_ACT` target — but it
does so by **re-projecting evidence Opencomplai already gathers for the EU AI Act**,
not by measuring anything new.

## No new scanner was added

This is the single most important fact about this page: **CP-16 added zero new
scanners, evaluators, or probes.** Every NIST AI RMF subcategory verdict
`opencomplai gaps --target NIST_AI_RMF` prints is a re-statement of a rule,
obligation, scan, or evaluator result that `opencomplai gaps`/`check` already
compute for `EU_AI_ACT` — the exact same `ArticleGapStatus` rows described in
[Control Codes → Principles → Articles](eu-ai-act-principles.md). Nothing was built
that inspects your system, your code, or your model any differently for NIST AI RMF
than it already does for the EU AI Act.

## How the re-projection works

1. `opencomplai check`/`gaps` computes a per-EU-AI-Act-article
   `Met`/`Partial`/`Missing`/`Unverified` status from your rule engine, obligation
   catalogue, code scan, and pipeline evaluator results — this is the ordinary
   `GapReport` (`opencomplai_core.gap_report`).
2. `data/framework_crosswalk.json` (added by an earlier epic, D-3a) links each EU AI
   Act article to a NIST AI RMF 1.0 **category** (e.g. `Art. 17` → `GOVERN 1`), with a
   `source` and a `confidence` (`low` or `medium` today — nothing in the crosswalk
   claims `high`).
3. `opencomplai_core.nist_rmf_report.build_nist_rmf_report` walks every one of the 72
   subcategories in `data/nist_ai_rmf_subcategories.json` (the RMF 1.0 core taxonomy —
   Govern/Map/Measure/Manage, sourced from NIST's own published core tables) and, for
   each one:
   - finds every crosswalk row whose NIST category matches this subcategory's parent
     category;
   - looks up the `GapReport` status of each of those EU AI Act articles;
   - reports the **worst** status among them (the same worst-case rollup
     `principle_report.py` already uses for the 6 EU Trustworthy AI principles), and
   - reports the crosswalk's own mapping `confidence`, **never upgraded**.

A subcategory whose category has no crosswalk row at all — as of this epic, that is
every `MANAGE` subcategory, since the crosswalk has no `MANAGE`-mapped article yet —
is reported `Unverified` with no confidence, not a guessed verdict. The same applies
when a mapped article simply wasn't part of a given run's `GapReport`.

## The crosswalk maps at category granularity

`data/framework_crosswalk.json` links an EU AI Act article to a NIST **category**
(e.g. `GOVERN 1`, `MAP 2`), not to an individual subcategory (`GOVERN 1.3`). Every
subcategory under a mapped category therefore gets the *same* re-projected verdict —
this is the honest consequence of the crosswalk's own resolution, not something the
re-projection invents. Run `opencomplai gaps --target NIST_AI_RMF` to see this
directly: `GOVERN 1.1` through `GOVERN 1.7` all carry the same status, confidence, and
EU AI Act citation whenever `Art. 17` is their only contributing article.

## Reading a subcategory row

```text
$ opencomplai gaps --manifest system-manifest.json --target NIST_AI_RMF

Subcategory   Status    Mapping conf.   From (EU AI Act)   Rationale
GOVERN 1.1    MISSING   medium          Art. 17            Re-projected via
                                                            data/framework_crosswalk.json
                                                            (GOVERN 1, mapping
                                                            confidence=medium) from
                                                            existing EU AI Act evidence:
                                                            Art. 17 -> missing
                                                            (source=obligation,
                                                            evidence=provider_qms).
```

Every row's `Rationale` names the exact EU AI Act article(s), their gap-report status,
and the evidence reference (rule id, obligation id, evaluator id, or scan finding) the
verdict was derived from — the citation trail. `--output json` carries the same fields
under `nist_rmf_report.subcategories[].source_eu_ai_act_articles` on both `opencomplai
gaps --target NIST_AI_RMF` and `opencomplai check --with-gaps` (the latter only when
the manifest's `compliance_target` is `NIST_AI_RMF`).

## Honesty guarantees

- **`needs_founder_review` is always `true`.** Every subcategory verdict inherits this
  from the crosswalk row(s) it was re-projected through — this content has not been
  confirmed by a human compliance/legal reviewer.
- **Confidence never gets upgraded.** A subcategory backed by a `low`-confidence
  crosswalk row is reported at `low` mapping confidence, regardless of how "measured"
  the underlying EU AI Act rule/evaluator evidence is. `confidence_label` is always
  `heuristic_estimate` for a re-projected verdict — never a legal determination.
- **An uncovered subcategory is `Unverified`, never fabricated.** If the crosswalk has
  no row for a subcategory's category, or the mapped article isn't present in the
  current run, the verdict says exactly that instead of guessing.
- **ISO/IEC 42001 stays mapped-only.** The same crosswalk cites an ISO/IEC 42001:2023
  clause per article (the "Mapped" column in `opencomplai gaps`'s default `EU_AI_ACT`
  output), but no verdict is computed for it — only `EU_AI_ACT` and `NIST_AI_RMF` are
  *evaluated* targets.

## A living framework

NIST AI RMF 1.0 (NIST AI 100-1, published January 2023) is the version this taxonomy
tracks. The White House's "America's AI Action Plan" (2025) directed NIST to revise
the AI RMF to remove references to misinformation, diversity/equity/inclusion, and
climate change; that revision had not been published as of the taxonomy's last
research date (see `data/nist_ai_rmf_subcategories.json`'s `_meta.researched_at` and
`_meta.pending_revision_caveat`). `GOVERN 3` (workforce diversity/equity/inclusion) and
`MEASURE 2.12` (environmental impact) are the subcategories most likely to move if and
when that revision publishes — re-verify the taxonomy against NIST's current core
tables before treating it as durable reference material.

## Where this lives in the codebase

| Concern | File |
|---|---|
| RMF 1.0 subcategory taxonomy | `packages/core/src/opencomplai_core/data/nist_ai_rmf_subcategories.json` |
| Taxonomy loader | `packages/core/src/opencomplai_core/nist_ai_rmf_subcategories.py` |
| EU AI Act ↔ NIST/ISO crosswalk | `packages/core/src/opencomplai_core/data/framework_crosswalk.json` |
| Re-projection (coverage rule) | `packages/core/src/opencomplai_core/nist_rmf_report.py` |
| CLI surface | `opencomplai gaps --target NIST_AI_RMF`, `opencomplai check --with-gaps` |

See [Control Codes → Principles → Articles](eu-ai-act-principles.md) for the EU AI Act
evidence this page's verdicts are derived from, and run `opencomplai gaps --target
NIST_AI_RMF` against your own manifest to see the re-projection applied to your system.
