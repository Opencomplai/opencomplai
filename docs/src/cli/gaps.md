# `opencomplai gaps`

Print a per-article EU AI Act gap report: for every tracked article, whether it is
**Met**, **Partial**, **Missing**, or **Unverified**, and which subsystem produced
that status (rule, obligation, scan, evaluator, or artifact probe).

**What:** a readable coverage board for humans and CI dashboards.

**When:** after you have a manifest (and optionally a scan report / sample set).

**Don't:** treat heuristic/partial rows as legal certification. Statuses include
honesty labels (`heuristic_estimate`, `not_assessed`, `measured`).

`gaps` is **informational only and never gates CI**; the exit-code contract stays
with `opencomplai check`.

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
| `--output` / `-o` | `human` | `human` or `json` (JSON is wrapped in a versioned envelope — not a signed artifact) |

## Understanding gap statuses

| Status | Meaning |
|---|---|
| **MET** | The mapped rule passed, or the mapped scan/evaluator source found no discrepancy. |
| **PARTIAL** | A mapped evaluator returned a `warn` outcome. |
| **MISSING** | A mapped rule failed, a scan found a discrepancy against the declared purpose, or a mapped evaluator failed. |
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

## Next step

Run `opencomplai recommend` to generate copy-paste remediation templates for every
`MISSING`/`PARTIAL` row in the gap report — see [recommend](recommend.md).
