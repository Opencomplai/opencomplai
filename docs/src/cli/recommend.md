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
| `--output` / `-o` | `./fixes` | Directory to write remediation templates to |

## What gets written

One file per `MISSING`/`PARTIAL` article row, named `<article-slug>-<template_id>.md`
(e.g. `art6-annex_iii_applicability_note.md`). `MET` and `UNVERIFIED` rows produce no
output — if your gap report has none, `recommend` prints
`No Missing/Partial gap-report rows — nothing to recommend.` and exits cleanly.

When the manifest targets a natively evaluated framework besides the EU AI Act, its
rows follow the EU AI Act's; a row with no template of its own gets
`generic_requirement.md`, written as `<fw>--<id>-generic_requirement.md` for
`<FW>:<id>`. NIST AI RMF rows are re-projected from EU AI Act evidence, so they add no
files. With `--gap-report`, the same frameworks are read from the file's `frameworks`
block.

Every rendered template embeds the triggering `{{article}}`, `{{status}}`, `{{source}}`,
`{{evidence_ref}}`, and `{{rationale}}`, so the output file is traceable back to the
exact `opencomplai gaps` row that produced it.

## The 6 templates

| Article(s) | Template | What it gives you |
|---|---|---|
| Art. 4 | AI Literacy Checklist | A checklist stub for the Art. 4 AI-literacy obligation. |
| Art. 5, Art. 6 | Annex III Applicability Note | A note framing why the system was flagged as prohibited-practice or Annex III high-risk, and what to confirm. |
| Art. 10, Art. 15 | Risk Register Entry | A risk-register stub covering data-governance (Art. 10) or robustness/safety (Art. 15) findings. |
| Art. 11, Art. 12 | Logging / Event Capture Stub | A stub for the record-keeping and logging obligations. |
| Art. 25 | Human Oversight Checklist | A checklist for the substantial-modification / human-oversight obligation. |
| Art. 50 | Transparency Notice | A disclosure-notice stub for the Article 50 transparency obligation. |
| Art. 53, Art. 55 | GPAI Obligation Stub | A stub for GPAI provider (Art. 53) or systemic-risk (Art. 55) obligations. |

Each template is a **starting point for your compliance team to fill in**, not a
generated legal document — treat the output the same way you'd treat a linter's
auto-fix suggestion: a scaffold, not a substitute for review.

## Next step

Once remediation is underway, run `opencomplai report` to render a single shareable
HTML/PDF document combining the manifest, rule results, gap report, and eval/scan
summaries — see [report](report.md).
