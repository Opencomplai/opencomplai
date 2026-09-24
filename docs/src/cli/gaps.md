# `opencomplai gaps`

Print a gap report for every target framework (the EU AI Act by default): for
every tracked requirement, whether it is **Met**, **Partial**, **Missing**, or
**Unverified**, and which subsystem produced that status (rule, obligation, scan,
evaluator, or artifact probe).

**What:** a readable coverage board for humans and CI dashboards.

**When:** after you have a manifest (and optionally a scan report / sample set).

**Don't:** treat heuristic/partial rows as legal certification. Statuses include
honesty labels (`heuristic_estimate`, `not_assessed`, `measured`).

`gaps` is **informational only and never gates CI**; the exit-code contract stays
with `opencomplai check`. A framework that `opencomplai.yaml` gates (see
[`check`](check.md#gating-other-frameworks)) says so under its table.

## Usage

=== "macOS / Linux"
    ```bash
    opencomplai gaps --manifest system-manifest.json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai gaps --manifest system-manifest.json
    ```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--manifest` / `-m` | `system-manifest.json` | System manifest path |
| `--commit-ref` | `HEAD` | Commit reference for provenance |
| `--scan-report` | *(none)* | Path to a `CorroborationReport` JSON from a prior `opencomplai scan --output json` — resolves scan-sourced article rows |
| `--sample-set` | *(none)* | Path to an `EvalSampleSet` JSON — resolves evaluator-sourced article rows (safety, bias, data-leakage) |
| `--repo-root` | `.` | Repo root for artifact path probes (Arts. 9/13/14/16/24/43) |
| `--target` | manifest | Framework to assess (`EU_AI_ACT`, `NIST_AI_RMF`); repeat for several. Replaces the manifest's `compliance_targets`, else its `compliance_target`. More than one target prints a table per framework and adds a `frameworks` block to the JSON |
| `--output` / `-o` | `human` | `human` or `json` (JSON is wrapped in a versioned envelope — not a signed artifact) |

## Understanding gap statuses

| Status | Meaning |
|---|---|
| **MET** | The mapped rule passed, or the mapped scan/evaluator source found no discrepancy. |
| **PARTIAL** | A mapped evaluator returned a `warn` outcome. |
| **MISSING** | A mapped rule failed, a scan finding in a mapped signal category maps to an Annex III area the declared purpose does not cover (a scan discrepancy), or a mapped evaluator failed. |
| **UNVERIFIED** | No automated source was run for this article in this invocation — not the same as "failing." An obligation-only article (e.g. Art. 11, Art. 12) is always `UNVERIFIED`, since Opencomplai has no automated check for it; a rule/scan/evaluator-backed article is `UNVERIFIED` only when you didn't supply the input needed to resolve it (`--scan-report` and/or `--sample-set`). |

**This distinction is deliberate, not a limitation to work around silently:** the rule
engine alone cannot see everything. An article whose only mapped source is a pipeline
evaluator (e.g. Art. 15's `EVAL_SAFETY_LEXICAL_V1`) will read `UNVERIFIED` — not
`MISSING` — until you pass `--sample-set`. Passing more inputs turns more rows from
`UNVERIFIED` into a real `MET`/`PARTIAL`/`MISSING` verdict; it never turns a real
`MISSING` back into `UNVERIFIED`.

## Example: rule-sourced and evaluator-sourced rows together

Given a manifest with `intended_purpose: "recruitment screening of candidates"` (an
Annex III high-risk use case) and a `--sample-set` whose outputs contain an
adversarial-prompt fixture that fails `EVAL_SAFETY_LEXICAL_V1`:

=== "macOS / Linux"
    ```bash
    opencomplai gaps --manifest system-manifest.json --sample-set eval-set.json --output json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai gaps --manifest system-manifest.json --sample-set eval-set.json --output json
    ```

```json
{
  "system_id": "hiring",
  "commit_ref": "HEAD",
  "generated_at": "2026-07-12T10:00:00+00:00",
  "articles": [
    {
      "article": "Art. 6",
      "status": "missing",
      "source": "rule",
      "evidence_ref": "EU_AIA_ART6_HIGH_RISK",
      "rationale": "Intended purpose matches Annex III employment category."
    },
    {
      "article": "Art. 15",
      "status": "missing",
      "source": "evaluator",
      "evidence_ref": "sha256:...",
      "rationale": "EVAL_SAFETY_LEXICAL_V1 (NIST AI RMF MEASURE 2.6 / EU AI Act Art. 15 (robustness)): fail."
    },
    {
      "article": "Art. 11",
      "status": "unverified",
      "source": "obligation",
      "evidence_ref": "none",
      "rationale": "No source data supplied for this article in this run."
    }
  ],
  "evidence_hashes": [],
  "principle_summary": { "principles": [ "..." ] }
}
```

The `Art. 6` row is **rule-sourced** — it comes from the static rule engine and needs no
extra input. The `Art. 15` row is **evaluator-sourced** — it only resolves to a real
verdict (here, `MISSING`) because `--sample-set` was supplied; run `gaps` without
`--sample-set` against the same manifest and Art. 15 reads `UNVERIFIED` instead. This is
the mechanism behind [1.5 in the roadmap]: `--sample-set` affects `gaps` output the same
way it affects `check --sample-set`.

## Principle Summary

Every `gaps` invocation (human or JSON) also rolls the per-article statuses up into the
6 **EU Trustworthy AI principles** (Technical Robustness & Safety, Privacy & Data
Governance, Transparency, Diversity/Non-discrimination/Fairness, Societal &
Environmental Wellbeing, Accountability). Each principle shows the **worst-case status**
across its mapped articles — the same "MISSING beats PARTIAL beats UNVERIFIED beats MET"
convention used for individual article rows.

Human output:

```text
Principle Summary

Principle                                  Status       Articles
Technical Robustness and Safety            MISSING      Art. 15, Art. 25
Privacy and Data Governance                UNVERIFIED   Art. 10
Transparency                               UNVERIFIED   Art. 12, Art. 50
Diversity, Non-discrimination and Fairness MISSING      Art. 5, Art. 6, Art. 10
Societal and Environmental Wellbeing       UNVERIFIED   Art. 5
Accountability                             UNVERIFIED   Art. 4, Art. 11, Art. 53, Art. 55
```

See [EU AI Act Principles](../concepts/eu-ai-act-principles.md) for the full
article-to-principle mapping and which rule/obligation/scan/evaluator backs each
article.

`principle_summary` is an **additive, optional field** on `GapReport` — existing
`gaps --output json` consumers that don't read it are unaffected by its presence.

## Several frameworks

With exactly one target, `EU_AI_ACT` or `NIST_AI_RMF`, `gaps` prints and returns what
it always has: the EU AI Act table above, or the NIST AI RMF subcategory table (see
[NIST AI RMF](../concepts/nist-ai-rmf.md)). With any other set, from the manifest's
`compliance_targets` or from repeated `--target`, it prints one table per framework in
target order. A framework other than the EU AI Act gets a table of its own, with
prefixed requirement ids (`NIST_AI_RMF:GOVERN 1.1`), the requirements excluded in the
manifest's `framework_inputs` and their reasons, a note when `opencomplai.yaml` gates
it, and the framework-neutral disclaimer.

=== "macOS / Linux"
    ```bash
    opencomplai gaps --target EU_AI_ACT --target NIST_AI_RMF --output json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai gaps --target EU_AI_ACT --target NIST_AI_RMF --output json
    ```

The JSON `payload` keeps the EU AI Act report at its top level (and `nist_rmf_report`
when `NIST_AI_RMF` is a target) and adds a `frameworks` block, one framework report
per target:

```json
{
  "system_id": "loan-decision-model",
  "articles": ["... the EU AI Act rows, as above ..."],
  "nist_rmf_report": {"subcategories": ["..."]},
  "frameworks": {
    "EU_AI_ACT": {"framework": "EU_AI_ACT", "derived_from": null, "report": {"...": "..."}},
    "NIST_AI_RMF": {
      "framework": "NIST_AI_RMF",
      "label": "NIST AI RMF 1.0 (derived from EU AI Act evidence)",
      "data_version": "9513768b2196",
      "derived_from": "EU_AI_ACT",
      "disclaimer_ref": "DISCLAIMER_V2",
      "gated": false,
      "excluded": {"NIST_AI_RMF:MAP 1.1": "Internal tool with no external users"},
      "report": {
        "articles": [
          {
            "article": "NIST_AI_RMF:GOVERN 1.1",
            "status": "missing",
            "source": "crosswalk",
            "evidence_ref": "Art. 5, Art. 9, Art. 11, Art. 16, Art. 17",
            "confidence_label": "heuristic_estimate",
            "disclaimer_ref": "DISCLAIMER_V2"
          }
        ]
      }
    }
  }
}
```

The envelope carries the framework-neutral disclaimer for such a run. An unknown
target, a `framework_inputs` key that is not a known framework, or a
`framework_inputs` entry that names an id the framework does not have, exits `2`. See [Frameworks](../frameworks/index.md) for exclusions and attestations.

## Next step

Run `opencomplai recommend` to generate copy-paste remediation templates for every
`MISSING`/`PARTIAL` row in the gap report — see [recommend](recommend.md).
