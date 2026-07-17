# Documentation Update Plan — New Features from the 2026-07-11/12 Feature Roadmap Run

Source of truth for this plan: `logs/autonomous-exec/STATUS-LEDGER.md`, `BLOCKERS.md`, `HANDOFF.md`,
and `EXECUTION-PLAN-opencomplai-features.md`. All 19 deliverables below are implemented in the working
tree and **uncommitted** — this plan assumes they land on `main` before or alongside the docs work.

Nothing here is committed to git yet. Docs work should target `docs/src/` (MkDocs / Material) and
package READMEs, matching the existing site structure in `mkdocs.yml`.

---

## How to use this plan

Each section below is one shippable doc unit: what feature it documents, which nav page(s) it touches
(new or existing), what source files ground the content, and what to verify before publishing. Work
top-to-bottom by phase — P0 items are the highest-traffic new commands, so they unblock the most
"how do I..." support burden if documented first.

---

## Phase 0 — Docs infrastructure decisions (do this first)

- [x] Decide nav placement for 4 new CLI commands (`gaps`, `recommend`, `report`, and the extended
      `scan`/`eval` flags). Added a new **CLI Reference** top-level nav section in `mkdocs.yml`.
  - Discovery during execution: `docs/src/cli/` already contained **11 existing pages**
    (`scan.md`, `check.md`, `init.md`, `checker.md`, `dashboard.md`, `docs-generate.md`,
    `exit-codes.md`, `risk-classify.md`, `sync-metadata.md`, `validate-manifest.md`,
    `verify-output.md`) that were **not wired into `mkdocs.yml` nav at all** — a pre-existing gap
    unrelated to this run. The new CLI Reference nav section includes all 11 existing pages plus
    the 3 new ones (`gaps.md`, `recommend.md`, `report.md`) and a new `eval.md` (see 2.6/3.1).
- [x] Confirmed: CLI docs live under their own **CLI Reference** top-level nav section (not nested
      under `Guides/` or `api/`). `Guides/` keeps workflow-level content (customer workflow, CI
      integration, pre-commit, configuration, SARIF); `CLI Reference` is pure command/flag reference.

---

## Phase 1 — P0 Adoption features (document first — highest visibility)

### 1.1 PyPI release / install path
**What shipped:** `README.md` Quick Start already updated to lead with `pip install opencomplai`
(previously build-from-source first). No new page needed — verify `getting-started/installation.md`
and `getting-started/quick-start.md` match the new README wording (they may still describe the old
build-from-source-first flow).
- [x] Audited: `installation.md`/`quick-start.md` already led with `pip install opencomplai` and cited
      "0.1.2 latest release", consistent with the README/CHANGELOG wording — no edit needed.
- [x] Decision (confirmed with user): mirror README's current wording rather than hedge or block on
      PyPI verification — a human is expected to verify/commit before merge. No separate "once
      published" caveat added in docs/src/.

### 1.2 `opencomplai gaps` command (NEW)
**What shipped:** New CLI command producing a `GapReport` (article → MET/PARTIAL/MISSING/UNVERIFIED,
citing the rule/obligation/scan/evaluator source). Flags: `--manifest`, `--commit-ref`, `--scan-report`,
`--sample-set`, `--output`. Also a `--with-gaps` opt-in flag added to the existing `check` command.
- [x] New page written: `docs/src/cli/gaps.md` (wired into new CLI Reference nav) covering:
  - Status table (MET/PARTIAL/MISSING/UNVERIFIED) with the "rule engine alone can't see everything"
    honesty note.
  - Full flag table, JSON example with both a rule-sourced and evaluator-sourced row (satisfies 1.5).
  - Principle Summary section + cross-link to `concepts/eu-ai-act-principles.md` (satisfies 3.2).
- Grounding files: `packages/core/src/opencomplai_core/gap_report.py`,
  `packages/core/src/opencomplai_core/data/gap_article_map.json`, `models.py` (`GapReport`,
  `ArticleGapStatus`, `GapStatus`).

### 1.3 `opencomplai recommend` command (NEW)
**What shipped:** Reads a `GapReport` (or builds one inline with the same flags as `gaps`) and emits
one Markdown remediation file per non-MET article, from 6 templates (logging/event capture,
transparency notice, human oversight checklist, risk register entry, Annex III applicability note,
GPAI Art.53/55 obligation stub).
- [x] New page written: `docs/src/cli/recommend.md` — full flag table, standalone-vs-piped usage
      patterns, and a table of all 6 templates with what each gives you.
- [x] Air-gap/no-network/no-model-call callout added as a tip box at the top of the page.

### 1.4 Framework AST detection (`--framework-detectors`)
**What shipped:** New opt-in scan flag that detects real *instantiation + invocation* of LangChain
(`AgentExecutor`), CrewAI (`Crew`), AutoGen (`ConversableAgent`), and LangGraph (`StateGraph`) objects
via AST analysis — distinct from (and more precise than) the pre-existing lexical `import` scan.
- [x] Updated `docs/src/cli/scan.md` with a `--framework-detectors` section: recognized-classes table,
      confidence/reachability behavior, and the known v1 single-function/module-scope limitation.
- [x] Updated `concepts/evidence.md` with a new "Scanner signal categories and detectors" section
      documenting `SignalCategory.AGENT_FRAMEWORK` / `DET_FRAMEWORK_AST_V1`.

### 1.5 Eval results surfaced in `gaps`
**What shipped:** No new command — `gaps` (1.2) already surfaces evaluator failures (e.g. an
adversarial-prompt fixture failing `EVAL_SAFETY_LEXICAL_V1`) as MISSING articles citing the
evaluator's `evidence_hash` and `reference` string. Purely a behavior note to fold into 1.2's page —
no standalone doc unit needed.
- [x] Done as part of 1.2's page (`cli/gaps.md`) — example includes both a rule-sourced (Art. 6) and
      evaluator-sourced (Art. 15, `EVAL_SAFETY_LEXICAL_V1`) row with explanatory text.

### 1.6 `opencomplai report` command (NEW)
**What shipped:** Renders a human-readable HTML or PDF compliance report from a `ScanStatusArtifact`
(+ optional `GapReport`). PDF path reuses the existing `fpdf2`-based renderer used by the checker
widget (no second PDF toolchain).
- [x] New page written: `docs/src/cli/report.md` — full flag table, HTML-vs-PDF extension-inference
      note, and a "getting the richest report" section using `check --with-gaps --scan`.
- [x] Read-only/no-network tip box added, consistent in style with `recommend.md`'s callout.

---

## Phase 2 — P1 Eval depth features

### 2.1 `scan --quick` (NEW flag)
**What shipped:** Discovery-only scan mode: no manifest required, forces `fail_on=none`,
`emit_evidence=False`, `enqueue_review=False`, always exits 0, prints a suggested `opencomplai init`
follow-up. Runs in ~0.37s on a small fixture repo — meant as a zero-friction first command for new
users (and the thing the pre-commit hook in 2.2 calls).
- [x] Added a "Try it with zero setup first" section to `quick-start.md`, positioned before
      "Initialise your system manifest" — the literal first command shown.
- [x] Contrast with `check` stated explicitly in both `quick-start.md` and `cli/scan.md`'s
      `--quick` section.

### 2.2 Pre-commit hook definitions (NEW file: `.pre-commit-hooks.yaml`)
**What shipped:** Two hook definitions consumers can reference from their own
`.pre-commit-config.yaml`: `opencomplai-quick-scan` (calls `scan --quick`) and `opencomplai-check`
(the full CI gate).
- [x] New page written: `docs/src/guides/pre-commit.md`, with the consumer-side YAML snippet and both
      hook IDs documented (`opencomplai-quick-scan`, `opencomplai-check`).
- [x] Pre-publish gate flagged explicitly: page opens with a `!!! warning` callout stating the
      end-to-end `pre-commit run --all-files` acceptance test has not yet been run against a published
      release, and gives the verification steps to run before relying on it in production.

### 2.3 Adversarial / jailbreak evaluator (NEW: `EVAL_ADVERSARIAL_V1`)
**What shipped:** New evaluator pairing `prompts`↔`outputs` by index to detect whether a
known-adversarial prompt produced a compliant (resisted) vs. non-compliant output. Distinct from the
pre-existing lexical `SafetyEvaluator` injection/jailbreak-marker scan.
- [x] Created `docs/src/concepts/evaluators.md` (new nav entry under Concepts) enumerating all 5
      registered evaluators, with a dedicated comparison table + prose explaining the
      `EVAL_ADVERSARIAL_V1` vs. `EVAL_SAFETY_LEXICAL_V1` distinction.

### 2.4 Bias/fairness bundled probe (NEW, synthetic — read BLOCKERS.md before writing this one)
**What shipped:** An opt-in synthetic bundled bias probe (`bundled_bias_probe.json`, 40 rows, 2
synthetic groups), NOT a real BBQ/BOLD/CAB dataset subset. Triggered only when
`threshold_overrides["use_bundled_bias_probe"] == 1.0` and no custom sample set is supplied.
- [x] Documented in `concepts/evaluators.md` under "Bias/fairness — bundled synthetic probe (not a
      real benchmark)" with a `!!! warning` callout stating explicitly it is not BBQ/BOLD/CAB, using
      close to the suggested phrasing.

### 2.5 Calibration evaluator (NEW: `EVAL_CALIBRATION_V1`)
**What shipped:** New opt-in evaluator computing Expected Calibration Error (ECE) over
`predictions`/`labels`, gated behind `threshold_overrides.include_calibration == 1.0` (skipped by
default, zero cost when not requested).
- [x] Added to `concepts/evaluators.md` with a plain-language ECE definition, the opt-in gating
      requirement, and the PASS/WARN/FAIL/SKIPPED outcome table.

### 2.6 Multi-provider model eval (NEW flags on `eval`: `--provider`, `--model`, `--provider-api-key-env`)
**What shipped:** Optional live-model evaluation path (OpenAI-compatible providers) alongside the
existing local/deterministic evaluators. Every provider-backed result is explicitly tagged
non-deterministic in output, and this code path is never imported by the `check` (CI gate) path.
- [x] New page written: `docs/src/cli/eval.md` (new, since no `eval` CLI reference page existed before
      this run) with a `!!! warning` callout using close to the suggested framing, plus the
      `deterministic: false` JSON tagging shown explicitly.
- [x] Env var pattern and supported-providers table included (`openai`, `openai_compatible`).

### 2.7 Provider/SDK detection breadth (data-only, `ai_signals.json` 13→22 tokens)
**What shipped:** No new command/flag — `scan`'s existing AI-SDK detection now recognizes 9 more
provider SDKs (fireworks-ai, perplexityai, ai21, stability-sdk, elevenlabs, deepgram, assemblyai,
google-cloud-aiplatform, ibm-watsonx-ai).
- [x] Neither `scan-workflow.md` nor `evidence.md` enumerated the SDK list, so added a short paragraph
      to `getting-started/scanner.md` (the user-facing scanner guide) instead, listing all 22
      recognized SDKs.

---

## Phase 3 — P2 Integration features

### 3.1 Inspect-AI eval bridge (structural only — read BLOCKERS.md before writing this one)
**What shipped:** New optional `inspect-bridge` extra (`pip install 'opencomplai-core[inspect-bridge]'`)
and a new `--suite inspect-ai` flag on `eval`. The bridge defines the full mapping contract
(`is_inspect_available()`, `eval_log_to_evaluator_result()`); `run_inspect_suite()` runs the
curated Inspect pin (see `concepts/inspect-bridge.md`).
- [x] Documented in `cli/eval.md` under "Inspect-AI eval bridge (`--suite inspect-ai`)",
      explaining install, curated tasks, and that the bridge never gates `check`.

### 3.2 EU AI Act principle dashboard (`principle_summary` on `gaps`)
**What shipped:** `gaps` output (human table + JSON) now includes a rollup of the 6 EU Trustworthy AI
principles (Technical Robustness & Safety, Privacy & Data Governance, Transparency, Diversity/
Non-discrimination/Fairness, Societal & Environmental Wellbeing, Accountability), each showing
worst-case status across its mapped articles.
- [x] Folded into `cli/gaps.md`'s "Principle Summary" section with example human-output table and
      cross-link to `concepts/eu-ai-act-principles.md`.
- [x] Backward-compatibility note included verbatim as its own paragraph.

### 3.3 SARIF export (`--sarif-output` on `scan`)
**What shipped:** New flag emitting a SARIF 2.1.0 document from scan evidence, for GitHub code
scanning / Security tab integration.
- [x] New page written: `docs/src/guides/sarif-integration.md`, with `--sarif-output` usage, a GitHub
      Actions snippet using `codeql-action/upload-sarif@v3`, a corroboration-only `!!! info` callout,
      and a field-mapping table (`ruleId`/`level`/`message`/`locations`/`properties`).

### 3.4 JS/TS repo scanning — design spike only (NOT implemented)
**What shipped:** `docs/design/js-ts-scanning-spike.md` — an internal design doc, not a feature.
- [x] Added a short "Roadmap: JS/TS repository scanning (design spike, not implemented)" section to
      `docs/src/contributing/index.md` (contributor-facing, not user-facing), pointing to
      `docs/design/js-ts-scanning-spike.md` and stating explicitly that `.js`/`.ts` detection does not
      work yet.

### 3.5 Project config file (`opencomplai.yaml`)
**What shipped:** New optional per-repo config file, auto-discovered from `--repo-root`, currently
supporting `scan.fail_on` and `scan.framework_detectors` defaults. Explicit CLI flags always override
config file values; config file overrides built-in defaults.
- [x] New page written: `docs/src/guides/configuration.md` — discovery rule, supported-keys table
      (explicit "this list will grow" note), precedence rule, and the exact worked example from the
      ledger (`fail_on: critical` in config + `--fail-on major` override).
- [x] "Behavior only, never a declaration" scope note added as a top-of-page `!!! info` callout, plus
      a comparison table against `system-manifest.json`/`.ocignore`/CLI flags.

### 3.6 Published EU AI Act principles page (ALREADY LIVE — no action needed)
**What shipped:** `docs/src/concepts/eu-ai-act-principles.md`, already generated and wired into
`mkdocs.yml`'s `Concepts` nav (confirmed present in current `mkdocs.yml:158` and file already exists
with full content). Auto-generated by `scripts/generate_principle_docs.py` from the same data
`gaps`'s `principle_summary` reads — regenerate this script's output (don't hand-edit the `.md`) any
time `eu_ai_act_principles.json` or `gap_article_map.json` changes.
- [x] Nothing to do here — this deliverable's docs artifact is done. Just remember: **never hand-edit
      `docs/src/concepts/eu-ai-act-principles.md` directly** — rerun
      `python scripts/generate_principle_docs.py` instead, or edits will be silently lost next
      regeneration.

---

## Suggested new nav structure (draft — for Phase 0 decision)

```yaml
  - CLI Reference:
    - Overview: cli/index.md
    - scan: cli/scan.md              # includes --quick, --framework-detectors, --sarif-output
    - check: cli/check.md            # includes --with-gaps
    - gaps: cli/gaps.md               # includes principle_summary
    - recommend: cli/recommend.md
    - report: cli/report.md
    - eval: cli/eval.md               # includes --provider/--model, --suite inspect-ai

  - Guides:
    - ...(existing)...
    - Pre-commit Integration: guides/pre-commit.md
    - Project Configuration: guides/configuration.md
    - CI Code Scanning (SARIF): guides/sarif-integration.md
```

## Cross-cutting doc-writing notes

- **Be honest about scope-limited deliverables.** Three features (2.4 bias probe, 3.1 Inspect-AI
  eval bridge, 3.4 JS/TS) are intentionally partial or non-functional today. Documenting them as fully
  shipped would create support burden and credibility risk — mark them "synthetic/placeholder,"
  "scaffolding, not yet functional," and "design spike, not implemented" respectively, per
  `BLOCKERS.md`.
- **The moat is a selling point, not just an engineering constraint** — several new features
  (`recommend`, `report`, framework AST detection) are explicitly deterministic/no-network/no-LLM.
  Worth a consistent callout box style across pages so customers evaluating for regulated/air-gapped
  environments can find this reassurance quickly.
- **Verify before publishing anything about 1.1 (PyPI) or 2.2 (pre-commit hook)** — both have
  outstanding human-only steps in `HANDOFF.md` that gate whether the documented behavior is actually
  live yet.
