# Frameworks

Opencomplai can assess one AI system against several frameworks side by side. The EU
AI Act is the default target; the table below gives each framework's status, its row
count and how many rows are checked from evidence.

Standing line: 15 frameworks by status, evaluated: EU AI Act, NIST AI RMF 1.0, ISO/IEC 42001:2023 AI management system, ISO/IEC 27090:2026 AI security guidance, ISO/IEC 27001:2022 information security management, SOC 2 Trust Services Criteria (not a SOC 2 report), NIS2 Directive (EU) 2022/2555 cybersecurity measures, DORA Regulation (EU) 2022/2554 digital operational resilience, EBA Guidelines on ICT, outsourcing and loan origination, EIOPA Opinion on AI governance and risk management, GDPR Regulation (EU) 2016/679, duties relevant to AI systems, Cyber Resilience Act Regulation (EU) 2024/2847, ETSI EN 304 223 baseline cyber security for AI, ISO/IEC 42005:2025 AI system impact assessment, ISO/IEC 23894:2023 AI risk management guidance.

## What each framework gets

<!-- status-table:start -->
| Framework | Key | Status | Rows | Checked from evidence | Unreviewed rows |
| --- | --- | --- | --- | --- | --- |
| EU AI Act | EU_AI_ACT | evaluated | 24 | 22 | 5 |
| NIST AI RMF 1.0 | NIST_AI_RMF | evaluated | 72 | 56 | 72 |
| ISO/IEC 42001:2023 AI management system | ISO_IEC_42001 | evaluated | 65 | 39 | 65 |
| ISO/IEC 27090:2026 AI security guidance | ISO_IEC_27090 | evaluated | 31 | 25 | 31 |
| ISO/IEC 27001:2022 information security management | ISO_IEC_27001 | evaluated | 118 | 43 | 118 |
| SOC 2 Trust Services Criteria (not a SOC 2 report) | SOC_2 | evaluated | 61 | 32 | 61 |
| NIS2 Directive (EU) 2022/2555 cybersecurity measures | NIS2 | evaluated | 21 | 16 | 21 |
| DORA Regulation (EU) 2022/2554 digital operational resilience | DORA | evaluated | 37 | 24 | 37 |
| EBA Guidelines on ICT, outsourcing and loan origination | EBA | evaluated | 25 | 7 | 25 |
| EIOPA Opinion on AI governance and risk management | EIOPA_AI | evaluated | 8 | 7 | 8 |
| GDPR Regulation (EU) 2016/679, duties relevant to AI systems | GDPR | evaluated | 21 | 18 | 21 |
| Cyber Resilience Act Regulation (EU) 2024/2847 | CRA | evaluated | 63 | 50 | 63 |
| ETSI EN 304 223 baseline cyber security for AI | ETSI_EN_304_223 | evaluated | 72 | 49 | 72 |
| ISO/IEC 42005:2025 AI system impact assessment | ISO_IEC_42005 | evaluated | 20 | 17 | 20 |
| ISO/IEC 23894:2023 AI risk management guidance | ISO_IEC_23894 | evaluated | 23 | 15 | 23 |
<!-- status-table:end -->

The status words and counts above come from the framework data, not from this page. The last
column counts rows flagged for founder review. Evaluated does not mean certified: nothing here is an audit, a
certification or a legal assessment. How a framework's rows are decided is on its own page,
linked under [Framework pages](#framework-pages).

`gaps --map-to DORA|EBA` is a separate, mapped-only feature: it adds a low-confidence citation per EU AI
Act article to the EU table and computes no status. See [Mapped regimes](../concepts/mapped-regimes.md).

The keys in the table are the only targets this release accepts. Any other key is an error: `gaps`,
`check` and `validate-manifest` exit `2`. None of these verdicts is a legal determination or a
certification.

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
decided by that evidence alone. From 0.16.0 that also covers a subcategory whose
mapped articles all do not apply in the run, according to a recorded checker session: such a row
reads Unverified until it is attested, and an attestation on a row that evidence decides is not
used (see [NIST AI RMF](../concepts/nist-ai-rmf.md)). `EU_AI_ACT` takes attestations only for the articles no code can
show: Art. 4 (AI literacy) and, from 0.16.0, Art. 20 (corrective actions and the duty
of information), under the unprefixed ids `Art. 4` and `Art. 20`. Art. 20 binds the provider of a
high-risk system, so a recorded checker session that did not record the provider high-risk
obligation moves it out of the gap table as not applicable.

Attestations can also come from an attestation bundle, merged in for the run; see
[Attestation bundles](more-packs.md#attestation-bundles).

`gaps`, and `check` when it assesses the targets (`--with-gaps` or a gate), exit `2`
when `framework_inputs` names an unknown framework, an id is not a requirement of that
framework, an exclusion reason is blank, an attestation is not accepted for that
requirement, or `framework_inputs` names `EU_AI_ACT` with an `excluded` or `scope` entry
or an attestation for any article other than Art. 4 (and, from 0.16.0, Art. 20).
An unknown field or an empty string inside a `framework_inputs` entry fails manifest
validation (exit `2`) for every command.

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
expressed per subcategory. From 0.16.0 it does so only through links at `medium`
confidence or better: an article linked at `low` confidence that reads Missing or Partial
makes the subcategory Unverified instead. See
[Gating other frameworks](../cli/check.md#gating-other-frameworks) for the full rules.

## Framework pages

- [EU AI Act](eu-ai-act.md), 24 rows.
- [NIST AI RMF 1.0](../concepts/nist-ai-rmf.md), 72 rows.
- [ISO/IEC 42001:2023 AI management system](iso-iec-42001.md), 65 rows.
- [ISO/IEC 27090:2026 AI security guidance](../concepts/iso-27090.md), 31 rows.
- [ISO/IEC 27001:2022 information security management](iso-iec-27001.md), 118 rows.
- [SOC 2 Trust Services Criteria (not a SOC 2 report)](soc-2.md), 61 rows.
- [NIS2 Directive (EU) 2022/2555 cybersecurity measures](nis2.md), 21 rows.
- [DORA Regulation (EU) 2022/2554 digital operational resilience](dora.md), 37 rows.
- [EBA Guidelines on ICT, outsourcing and loan origination](eba.md), 25 rows.
- [EIOPA Opinion on AI governance and risk management](eiopa-ai.md), 8 rows.
- [GDPR Regulation (EU) 2016/679, duties relevant to AI systems](gdpr.md), 21 rows.
- [Cyber Resilience Act Regulation (EU) 2024/2847](cra.md), 63 rows.
- [ETSI EN 304 223 baseline cyber security for AI](etsi-en-304-223.md), 72 rows.
- [ISO/IEC 42005:2025 AI system impact assessment](iso-iec-42005.md), 20 rows.
- [ISO/IEC 23894:2023 AI risk management guidance](iso-iec-23894.md), 23 rows.

Also:

- **EU AI Act:** the [applicability checker](../getting-started/eu-ai-act-checker.md),
  the [article-to-principle map](../concepts/eu-ai-act-principles.md), the
  [Annex IV coverage ledger](../concepts/annex-iv-coverage.md) and the
  [control codes](../concepts/control-codes.md).
- **All of them:** [Framework mappings](mappings.md), every requirement with its links to
  the other frameworks, and [More framework packs](more-packs.md).
- **Adding a framework:** [Adding framework packs](../contributing/adding-framework-packs.md).
