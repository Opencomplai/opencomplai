# Frameworks

Opencomplai can assess one AI system against several frameworks side by side. The EU
AI Act is the framework it evaluates natively and the default target; the table below
says exactly how each other framework is assessed.

Standing line: EU AI Act evaluated; NIST AI RMF derived per subcategory, attested where EU AI Act evidence is silent (unreviewed); ISO 42001, ISO 27090, ISO 27001, ISO 42005, ISO 23894, SOC 2, NIS2, DORA, EBA, EIOPA, GDPR, CRA and ETSI EN 304 223 native packs, attestation-led (unreviewed).

## What each framework gets

| Framework | Key | Status | How verdicts are produced |
|---|---|---|---|
| EU AI Act (Regulation (EU) 2024/1689) | `EU_AI_ACT` | **Evaluated** | Natively, per article: rules, obligations, the code scan, pipeline evaluators and documentation probes. The default target, and the only framework whose controls always gate `check`. |
| NIST AI RMF 1.0 (NIST AI 100-1) | `NIST_AI_RMF` | **Derived, per subcategory** | Each of the 72 subcategories lists the EU AI Act articles whose evidence is re-projected onto it. There is no NIST scanner. 15 subcategories have nothing in the EU AI Act evidence; they read **Unverified** until you record an attestation under `framework_inputs`. Every mapping is flagged for founder review. See [NIST AI RMF](../concepts/nist-ai-rmf.md). |
| ISO/IEC 42001:2023 | `ISO_IEC_42001` | **Attestation-led, partial** | Native rows per clause and Annex A control. Most rows are provider attestations that read **Unverified** until you record one under `framework_inputs`; four rows also look for a matching document, and the worse of the two wins. Nothing here certifies ISO/IEC 42001 conformity. Every row is flagged for founder review at low confidence. Each row links to the EU AI Act articles, NIST AI RMF subcategories and ISO/IEC 27090 clauses it relates to; see [Framework mappings](mappings.md). A clause is also still cited per EU AI Act article (the `Mapped` column of `opencomplai gaps`). |
| ISO/IEC 27090:2026 | `ISO_IEC_27090` | **Attestation-led guidance** | Native rows for the 31 guidance clauses on security threats to AI systems: practices, threats and mitigations. Every row takes a provider attestation. Four rows also take an output evaluator (prompt injection, injected output, sensitive output, red teaming), which can overrule the attestation when you supply an eval. Eight rows also look for supporting evidence in the repository (an SBOM or model pins, rate-limit code, a threat model, a red-team report, an event log): it never lowers a row, and an unattested row with such evidence stays **Unverified** (and names the file) rather than reading Met or failing a gate. ISO/IEC 27090 is guidance, so nothing here is a certification. Every row is flagged for founder review at low confidence. See [ISO/IEC 27090](../concepts/iso-27090.md). |
| ISO/IEC 27001:2022, SOC 2, NIS2, DORA, EBA guidelines, EIOPA AI Opinion, GDPR, Cyber Resilience Act, ETSI EN 304 223, ISO/IEC 42005:2025, ISO/IEC 23894:2023 | `ISO_IEC_27001`, `SOC_2`, `NIS2`, `DORA`, `EBA`, `EIOPA_AI`, `GDPR`, `CRA`, `ETSI_EN_304_223`, `ISO_IEC_42005`, `ISO_IEC_23894` | **Attestation-led** | Native rows per requirement, article, control or criterion. Every row takes a provider attestation and reads **Unverified** until you record one; a few also look for supporting evidence in the repository. Each row links to the EU AI Act articles and, for the security frameworks, the ISO/IEC 27001 Annex A controls it relates to. None of this is an audit, a certification or a legal assessment. Every row is flagged for founder review at low confidence. See [More framework packs](more-packs.md). |
| DORA and EBA citations | none | **Mapped only** | `gaps --map-to DORA\|EBA` still adds a low-confidence citation per EU AI Act article to the EU table. No status is computed. Flagged for founder review. See [Mapped regimes](../concepts/mapped-regimes.md). |

`EU_AI_ACT`, `NIST_AI_RMF`, `ISO_IEC_42001`, `ISO_IEC_27090` and the eleven keys above are the only targets this
release accepts. Any other key is an error: `gaps`, `check` and `validate-manifest` exit `2`. None of these verdicts
is a legal determination or a certification.

## Targeting several frameworks

List the frameworks in the manifest's `compliance_targets`:

```json
{
  "system_id": "loan-decision-model",
  "intended_purpose": "automated credit scoring for retail lending",
  "compliance_targets": ["EU_AI_ACT", "NIST_AI_RMF"],
  "high_risk_presumption": false,
  "commit_ref": "HEAD"
}
```

The frameworks a run assesses are resolved in this order:

1. `--target` on [`gaps`](../cli/gaps.md) or [`check`](../cli/check.md), repeated for
   several, replaces the manifest's list;
2. otherwise `compliance_targets`, in order, without duplicates (an empty list is
   rejected);
3. otherwise the single legacy `compliance_target` (default `EU_AI_ACT`).

Run [`opencomplai validate-manifest`](../cli/validate-manifest.md) to check the keys.

**Output for one framework is unchanged.** Without a gate, a run whose targets are
exactly `EU_AI_ACT`, or exactly `NIST_AI_RMF`, prints and writes exactly what earlier
releases did. Any other set adds:

| Command | Adds |
|---|---|
| `gaps` | One table per framework, in target order; `--output json` adds a `frameworks` block. |
| `check --with-gaps` | `framework_reports` in `compliance-artifact.json`. |
| `report` | One section per framework other than the EU AI Act. |
| `recommend`, `controls` | Remediation files and controls (ids prefixed `<FW>:`) for natively evaluated frameworks other than the EU AI Act. `ISO_IEC_42001` and `ISO_IEC_27090` ship in this release; NIST AI RMF, being derived, adds none. |

The EU AI Act report is always computed, even when it is not a target, because it is
the evidence the derived frameworks are built from. `gap_report` (EU AI Act) and
`nist_rmf_report` (whenever `NIST_AI_RMF` is a target) are always written as before;
`framework_reports` sits beside them, never in their place.

Each entry of `frameworks` and `framework_reports` is a framework report:

```json
{
  "framework": "NIST_AI_RMF",
  "label": "NIST AI RMF 1.0 (derived from EU AI Act evidence)",
  "data_version": "9513768b2196",
  "derived_from": "EU_AI_ACT",
  "disclaimer_ref": "DISCLAIMER_V2",
  "gated": false,
  "excluded": {"NIST_AI_RMF:MAP 1.1": "Internal tool with no external users"},
  "report": {"system_id": "loan-decision-model", "articles": ["..."]}
}
```

- `data_version` is a short hash of the framework data the verdicts came from, so two
  reports with the same value used the same mappings.
- `derived_from` names the framework whose evidence was re-projected; it is `null` for
  a natively evaluated framework.
- Requirement ids other than the EU AI Act's carry their framework as a prefix:
  `"Art. 9"` is the EU AI Act's, `"NIST_AI_RMF:GOVERN 1.1"` is NIST AI RMF's.
- The EU AI Act report keeps `DISCLAIMER_V1` ("does not certify EU AI Act
  compliance"); every other framework uses the neutral `DISCLAIMER_V2`, which does not
  certify compliance with any law, regulation or framework.

## Excluding requirements and recording attestations

Declarations about a framework go in the manifest, under `framework_inputs`, keyed by
framework. The manifest is the only place for compliance declarations;
[`opencomplai.yaml`](../guides/configuration.md) only configures how the tool behaves.

```json
{
  "compliance_targets": ["EU_AI_ACT", "NIST_AI_RMF"],
  "framework_inputs": {
    "NIST_AI_RMF": {
      "excluded": {
        "NIST_AI_RMF:MAP 1.1": "Internal tool with no external users"
      }
    }
  }
}
```

**`excluded`** maps a requirement id to the reason it does not apply. The row leaves
the report's rows and is listed under `excluded` with its reason instead; it never
fails a gate. For a natively evaluated framework it also becomes a waived control, with
the reason as the waiver rationale. Where a framework's rows depend on the system, a
`scope` block of yes/no answers excludes them for you with a generated reason (today
`ISO_IEC_27090`; see [ISO/IEC 27090](../concepts/iso-27090.md#scoping-rows-that-may-not-apply)).

**`attested`** maps a requirement id to a provider's statement that it is met:

```json
"attested": {
  "<FW>:<id>": {
    "statement": "The governance policy was approved by the board on 2026-09-01.",
    "attested_by": "Jane Doe",
    "attested_at": "2026-09-01"
  }
}
```

`attested_by` is a display name rather than an email address, because it is copied into signed
artifacts. An attestation may also carry `valid_until` (the last day it counts; from the next day the
row reads Unverified again), `evidence` (pointers to the documents behind it: a link, a file with its
SHA-256, or a record id) and `record_id` (set when it comes from an attestation bundle).

An attestation is recorded verbatim, and nothing checks it: it makes the requirement's
attestation source **Met**, with source `attestation` and confidence label `attested`.
A row takes the worst status of its sources, so an attested requirement that also has,
say, an artifact source stays Missing or Partial until that source is Met too. Only requirements whose
framework data takes an attestation accept one. `ISO_IEC_42001` and `ISO_IEC_27090`
take attestations on their requirements, with ids such as `ISO_IEC_42001:Clause 5.2` and
`ISO_IEC_27090:6.9`. `NIST_AI_RMF` takes attestations only on the subcategories the EU AI
Act evidence holds nothing for (for example `NIST_AI_RMF:MANAGE 2.1`); the others are
decided by that evidence alone. `EU_AI_ACT` takes attestations only for the articles no code can
show, which is Art. 4 (AI literacy) today, under the unprefixed id `Art. 4`.

Attestations can also come from an attestation bundle, merged in for the run; see
[Attestation bundles](more-packs.md#attestation-bundles).

`gaps`, and `check` when it assesses the targets (`--with-gaps` or a gate), exit `2`
when `framework_inputs` names an unknown framework, an id is not a requirement of that
framework, an exclusion reason is blank, an attestation is not accepted for that
requirement, or `framework_inputs` names `EU_AI_ACT` with an `excluded` or `scope` entry
or an attestation for any article other than Art. 4. An unknown field or an empty string
inside a `framework_inputs` entry fails manifest validation (exit `2`) for every command.

## Gating CI on another framework

The EU AI Act gates `check` as it always has. Another target framework gates only when
you opt in, in `opencomplai.yaml` or with `check --gate`:

```yaml
gate:
  frameworks: [NIST_AI_RMF]
  fail_on: missing   # or partial, or unverified
```

A Missing row of a gated framework (or, with `fail_on: partial`, a Missing or Partial
row) adds its prefixed id to `failed_controls` and turns `PASS` into `CONTROL_FAIL`
(exit `1`). Excluded, Unverified and Met rows never fail, except that `fail_on: unverified`
also fails a row that only an attestation can decide while it has no current attestation. Because NIST AI RMF rows are
re-projected from EU AI Act evidence, gating on it fails on the same underlying gaps,
expressed per subcategory. See [Gating other frameworks](../cli/check.md#gating-other-frameworks)
for the full rules.

## Framework pages

- **EU AI Act:** the [applicability checker](../getting-started/eu-ai-act-checker.md),
  the [article-to-principle map](../concepts/eu-ai-act-principles.md), the
  [Annex IV coverage ledger](../concepts/annex-iv-coverage.md) and the
  [control codes](../concepts/control-codes.md).
- **NIST AI RMF:** [how the re-projection works](../concepts/nist-ai-rmf.md).
- **ISO/IEC 27090:** [the AI security guidance pack](../concepts/iso-27090.md).
- **All of them:** [Framework mappings](mappings.md), every requirement with its links to
  the other frameworks.
- **Adding a framework:** [Adding framework packs](../contributing/adding-framework-packs.md).
