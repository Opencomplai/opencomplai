# `opencomplai recommend`

Write one remediation file per **Missing**/**Partial** requirement — Markdown
checklists or compile-checked Python examples. EU AI Act articles get their own
templates; see below for other frameworks.

**What:** starting-point fixes you can copy into your repo.

**When:** after `opencomplai gaps` shows actionable rows.

**Don't:** paste AGPL example Python into a proprietary product without counsel
review — each `.py` template carries an AGPL notice on purpose.

!!! tip "Deterministic, offline, no model calls"
    `recommend` is static content generation only. Safe for air-gapped environments.

## Two ways to run it

### 1. Standalone — builds a gap report inline

Point it at a manifest (and optionally a scan report / sample set), the same inputs
`opencomplai gaps` accepts:

=== "macOS / Linux"
    ```bash
    opencomplai recommend --manifest system-manifest.json --output ./fixes
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai recommend --manifest system-manifest.json --output ./fixes
    ```

### 2. Piped from `opencomplai gaps`

Reuse a gap report you already generated (avoids re-running the rule engine/scan/evals):

=== "macOS / Linux"
    ```bash
    opencomplai gaps --manifest system-manifest.json --output json > gap-report.json
    opencomplai recommend --gap-report gap-report.json --output ./fixes
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai gaps --manifest system-manifest.json --output json > gap-report.json
    opencomplai recommend --gap-report gap-report.json --output ./fixes
    ```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--manifest` / `-m` | `system-manifest.json` | System manifest path — used only when `--gap-report` is not supplied |
| `--commit-ref` | `HEAD` | Commit reference for provenance |
| `--gap-report` | *(none)* | Path to the output of a prior `opencomplai gaps --output json` (or a bare `GapReport` JSON); UTF-8, UTF-16 or the system code page, so a `>` redirect from any Windows shell works — when set, `--manifest`/`--scan-report`/`--sample-set` are ignored |
| `--scan-report` | *(none)* | Path to a `CorroborationReport` JSON — only used when `--gap-report` is not supplied |
| `--sample-set` | *(none)* | Path to an `EvalSampleSet` JSON — only used when `--gap-report` is not supplied |
| `--repo-root` | `.` | Repo root for artifact path probes (Arts. 9/13/14/16/17/24/43), including the Art. 17 per-clause QMS breakdown |
| `--output` / `-o` | `./fixes` | Directory to write remediation templates to |

## What gets written

One file per `MISSING`/`PARTIAL` article row, named `<article-slug>-<template_id>.md`
(e.g. `art6-annex_iii_applicability_note.md`). `MET` and `UNVERIFIED` rows produce no
output — if your gap report has none, `recommend` prints
`No Missing/Partial gap-report rows — nothing to recommend.` and exits cleanly.

An Art. 53 row also writes `art53-gpai_copyright_policy.md` and
`art53-gpai_training_summary.md`, both drafts flagged for founder and lawyer review.

When the manifest targets a natively evaluated framework besides the EU AI Act, its
rows follow the EU AI Act's; a row with no template of its own gets
`generic_requirement.md`, written as `<fw>--<id>-generic_requirement.md` for
`<FW>:<id>`. NIST AI RMF rows are re-projected from EU AI Act evidence, so they add no
files. With `--gap-report`, the same frameworks are read from the file's `frameworks`
block.

Every rendered template embeds the triggering `{{article}}`, `{{status}}`, `{{source}}`,
`{{evidence_ref}}`, and `{{rationale}}`, so the output file is traceable back to the
exact `opencomplai gaps` row that produced it.

## Templates

One template per article, as mapped in `template_map.json`. The Python templates are
compile-checked in the test suite; the rest are Markdown.

| Article(s) | Template id | What it gives you |
|---|---|---|
| Art. 4 | `ai_literacy_checklist` | A checklist stub for the Art. 4 AI-literacy obligation. |
| Art. 5 | `art5_prohibited_practices_screen` | A screen of the intended purpose against the Art. 5 list, with the reasoning recorded and matches escalated. |
| Art. 6 | `annex_iii_applicability_note` | A note framing why the system was flagged as Annex III high-risk, and what to confirm. |
| Art. 9 | `risk_register_entry` | A risk-register stub for risk-management findings. |
| Art. 10 | `art10_data_governance` | A table for data provenance, quality, bias examination and known gaps. |
| Art. 11 | `art11_technical_documentation` | The technical-file checklist; it starts with `opencomplai docs generate` for the Annex IV dossier. |
| Art. 12 | `event_logging` (Python) | A helper for the automatic event logging obligation. |
| Art. 13 | `instructions_for_use` | A 13-point checklist for the instructions for use that go to deployers; `opencomplai instructions generate` fills it from the manifest, see [instructions generate](instructions-generate.md). |
| Art. 14 | `oversight_checkpoint` (Python) | A human-oversight checkpoint. |
| Art. 15 | `art15_accuracy_robustness` | A record of accuracy metrics, robustness and cybersecurity measures, with the declared levels. |
| Art. 16 | `art16_provider_obligations` | A checklist of provider duties, each pointing at the article that owns it. |
| Art. 17 | `qms_outline` | A fill-in outline of the quality management system; `opencomplai qms generate` writes the filled version, see [qms](qms.md). |
| Art. 24 | `art24_distributor_obligations` | The checks a distributor makes before making a system available, and the duty to stop and inform on doubt. |
| Art. 25 | `art25_value_chain_responsibilities` | When a distributor, deployer or third party becomes the provider, and the substantial-modification sign-off checklist. |
| Art. 27 | `fria_template` | A fill-in template for the fundamental rights impact assessment; `opencomplai fria generate` drafts one, see [fria](fria.md). |
| Art. 43 | `art43_conformity_assessment` | A decision record for the assessment route (for counsel to confirm), the evidence to assemble, and re-assessment. |
| Art. 50 | `transparency_middleware` (Python) | An ASGI middleware that discloses AI interaction through response headers. |
| Art. 53, Art. 55 | `gpai_annex_documentation` | GPAI Annex XI/XII documentation checklist for provider (Art. 53) or systemic-risk (Art. 55) rows. These rows only appear for a recorded GPAI checker session. An Art. 53 row also writes two more drafts (see below). |
| Art. 26, 49 | `eu_obligation_action_plan` | A generic placeholder action plan, until the article gets a template of its own. |
| Art. 72 | `post_market_monitoring_plan` | A fill-in plan for post-market monitoring; save it as `docs/post-market-monitoring-plan.md`. |
| Art. 73 | `serious_incident_report` | A fill-in record of the facts of an incident; entries live in `incident-log.json` at the repository root. |

Each template is a **starting point for your compliance team to fill in**, not a
generated legal document — treat the output the same way you'd treat a linter's
auto-fix suggestion: a scaffold, not a substitute for review.

## Next step

Once remediation is underway, run `opencomplai report` to render a single shareable
HTML/PDF document combining the manifest, rule results, gap report, and eval/scan
summaries — see [report](report.md).
