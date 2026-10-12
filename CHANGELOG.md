# Changelog

All notable changes to Opencomplai are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this
project follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

## [0.11.0] — 2026-10-12

### Added

- A labelled benchmark measures how well the code-signal matcher points a
  program at an Annex III area. It scans 46 synthetic programs (29 across the
  eight areas, 17 with no area, including look-alikes such as a photo filter
  and a speech-to-text notes app) on two paths, `scan --ai-intent` and the
  default `check --scan`, and the new concepts page "Annex III detection
  benchmark" lists precision and recall per area. Overall it measures 73.3%
  precision and 75.9% recall on the intent path, and 44.4% and 13.8% on the
  default scan path. The programs are short, written for the benchmark and
  labelled by one author, so the table is a baseline for tuning the signals,
  not accuracy on real repositories. `packages/ai/tests/benchmark/run_benchmark.py`
  re-runs it offline from a source checkout.
- `opencomplai scan --propose` suggests a classification from your code; you
  confirm it. It turns on the intent analysis and writes
  `classification-proposal.json`: the most supported Annex III area (or
  `none`), the supporting and minority evidence with file and line, any
  prohibited-practice signals, and a confidence label (`none`, `low`, `medium`
  or `high`). The label counts the call sites that support the area; it is not
  a probability. The proposal stays unconfirmed, is not a legal determination,
  and needs `opencomplai-ai` (without it the command prints the install hint
  and exits 1). Under `--fail-on` the exit code can differ from a plain scan of
  the same repository, because the intent analysis is on.
- `opencomplai accept --proposal <file>` shows a proposal and, only after a
  yes, writes a signed `classification_proposal_confirmation` record with the
  proposal's digest and area. `--yes` confirms without the prompt for CI. A
  proposal that is not confirmed writes nothing and exits 1; one edited before
  confirming, or written for a different manifest, exits 2. Your signing key is
  used as for the other `accept` records. The record states only that a person
  confirmed the proposal as shown.

### Changed

- `check --scan` reports a `confirmed_proposal:<area>` row in the scan summary
  when a proposal you confirmed names an Annex III area that your declared
  purpose does not cover. The row counts as major under `--fail-on`, so
  `--fail-on major` and `--fail-on new-major` fail the check, while
  `--fail-on critical` and `none` do not. A missing, unconfirmed, edited or stale proposal changes nothing,
  and the declared purpose stays the source of the classification.
- The scanner's token dictionary (`ai_signals.json`) moves from 1.2.0 to
  1.3.0, so scan results for the same input can differ from 0.10.0. General
  audio and vision toolkits (`librosa`, `whisper`, `speechbrain`, `pyannote`,
  `mediapipe`) and the bare words `emotion` and `speaker` no longer map a
  program to the biometrics area; the toolkits still count as AI present, and
  specific names (`emotion_recognition`, `speaker_recognition`, `voiceprint`,
  `gait_recognition`, `fer` and a few more) were added. The vector-index
  packages `faiss` and `pgvector` no longer map a similarity search or a vector
  store to essential services; they too still count as AI present. `opencv`
  still maps to biometrics. On the benchmark's default scan path overall
  precision moves from 25.0% to 44.4% with recall unchanged.
- The declared-purpose hint of `scan --ai-intent` matches whole words, so
  "interface" is no longer read as "face" and "example" no longer as "exam".

## [0.10.0] — 2026-10-12

### Added

- `opencomplai export` writes one neutral evidence package from a compliance
  artifact written by `check --with-gaps`, as JSON or, with `--format csv`, as
  a flat CSV with one row per article. The package holds the system identity,
  the provenance and verdict fields, one entry per gap-report article and the
  original artifact embedded unchanged. `--artifact-out` writes the embedded
  artifact so `opencomplai verify` can check its signature offline. The command
  reads one file, writes only the paths you give it, and exits 0 once the
  package is written whatever verdict the artifact holds (2 when the input
  cannot be read). The JSON package is described by the new published schema
  `evidence_package.schema.json`.
- `check` stamps two optional fields into the artifact before signing:
  `tree_sha256`, a digest of the content of the tracked and the untracked,
  non-ignored files, and `tree_dirty`, true when a tracked file is modified or
  an untracked, non-ignored file exists. Both are left out outside a git
  repository or when git is not available.
- `opencomplai accept --exemption` writes a signed Article 6(3) exemption
  record that lists the grounds you relied on; give them with the repeatable
  `--ground` option, or they default to the grounds the checker kept in the
  manifest. The record states what you declared; it does not decide whether
  the exemption applies, and it is marked as needing legal review inside the
  signed bytes. The manifest's `checker_session` now keeps
  `derogation_grounds`, the Article 6(3) answers the last checker run relied
  on.
- `opencomplai check --require-exemption-record` is an opt-in gate. When the
  checker session relies on the Article 6(3) derogation (it lists
  `provider_art_6_4_registration`) and the repository holds no valid signed
  exemption record, `check` exits 1 with `EU_AIA_ART6_3_EXEMPTION_RECORD`. A
  record that is absent, unsigned, tampered, untrusted or stale (the manifest
  or its grounds changed after signing) counts as missing. Without the flag
  the exit code is unchanged.
- `opencomplai deployer-pack import` verifies a provider's deployer pack and
  records a reference to it (pack id, bundle hash, the provider's system id,
  `verified` or `unsigned`, and the signer key id) under the manifest's
  `imported_evidence` map. An invalid pack is refused before anything is
  written, and importing the same pack again changes nothing. The record is
  provenance only: `check` and `gaps` do not read it.
- The Annex IV dossier schema, `annex_iv_dossier.schema.json`, now has the
  stable `$id` `https://schemas.opencomplai.dev/annex_iv_dossier/v1`, as the
  artifact and gap report schemas do.

### Changed

- Upgrade note: older consumers of the artifact JSON must accept two new
  optional fields, `tree_sha256` and `tree_dirty`. A reader that rejects
  unknown keys will refuse a 0.10.0 artifact until it is widened; an artifact
  written outside a git repository does not carry them.
- The scan input digest now covers the content of the scanned files instead of
  the absolute path of the repository, so one tree gives one digest in two
  directories. The digest, and the scan id derived from it, differ from 0.9.2
  for the same tree.
- With `check --with-gaps`, the Art. 49 row of a session that lists
  `provider_art_6_4_registration` now also reports the state of the signed
  exemption record. A valid record does not make the row Met; the registration
  evidence still decides that. The manifest fingerprint now includes the
  Article 6(3) grounds when there are any, so changing a ground makes a signed
  exemption record stale (and a classification acceptance of that manifest
  too). A manifest without grounds keeps its fingerprint.

### Fixed

- A scoring or profiling signal in the code with no resolved Annex III area no
  longer maps to employment, essential services and law enforcement at once.
  It maps to no area until `--ai-intent` resolves one, and a resolved area
  still maps to exactly that one, so scan results for such code can differ
  from 0.9.2.
- Two simultaneous second approvals of one dual-control override could both be
  written to the ledger. The first now claims the override and the second
  answers 409 `ALREADY_COMPLETED`; the risk engine answers 503
  `AUDIT_UNAVAILABLE` when the evidence vault cannot be reached, and a failed
  ledger write releases the claim so a retry works. Upgrade the risk engine and
  the evidence vault together: a risk engine that talks to an older vault
  answers 503 for every second approval.
- Thirteen documentation links whose fragment pointed at a heading that does
  not exist now resolve, and the documentation build fails on a broken
  fragment.

## [0.9.2] — 2026-10-11

### Added

- The GitHub Action keeps the compliance artifact. `upload-artifact` (default
  `true`; set it to `"false"` to skip) uploads `compliance-artifact.json` as a
  workflow artifact kept for 90 days, named by the new `artifact-name` input
  (default `compliance-artifact-<commit sha>`). The new `sign` input signs the
  artifact when your signing key is in the environment (it warns and writes the
  artifact unsigned otherwise), the new `with-gaps` input adds the per-article
  gap report to it, and the new `artifact-file` output gives its path.
- Documentation: the `check` page now has a row for every option, the
  `OPENCOMPLAI_CHECK_ARGS` variable and a "Reports for CI" section; the agent
  commands page covers `attest`, `verify-log`, `import-log` and
  `dispute-report` with every option and exit code; the GitHub Action has its
  own guide page; the CI recipes guide adds a scheduled re-run, attaching the
  artifact to a release, recording agent decisions and scoring recorded model
  responses offline; the SDK reference documents `AgentDecisionLog`; and the
  works-alongside guide has a section on feeding the
  artifact to the governance platform you already use.

### Changed

- An agent mandate whose `expires_at` is before today (UTC date) now makes the
  Art. 26 row Missing, and a guardrail whose `evidence_ref`
  names a file that does not exist or lies outside the repository now makes
  the Art. 15 row Missing, so a gap report can show Missing where 0.9.1 did
  not.
- The backlog no longer shows a single application date for an article that two
  regulatory timeline entries date differently (for example an Annex III and an
  Annex I entry). Before, the earlier date was shown; now the deadline is empty
  and the row sorts with the undated ones. Entries with an unknown date are
  still ignored.
- `opencomplai scan` now maps a declared purpose to Annex III and Art. 5 areas
  with the same word-boundary matcher that `check` uses. A purpose such as
  "analytics reporting" no longer maps to employment in a scan while `check`
  reports minimal, and a keyword that is only part of a longer word no longer
  matches, so scan results on the same input can differ from 0.9.1.
- The adversarial evaluator (`EVAL_ADVERSARIAL_V1`, signature set 1.2.0) and
  the safety evaluator (`EVAL_SAFETY_LEXICAL_V1`, signature set 1.1.0) now
  normalise text (NFKC, zero-width characters removed, curly quotes folded)
  and match each signature as a whole word. "act as Daniel" no longer matches
  "act as dan", a refusal written with a curly apostrophe is recognised, and
  the safety injection and jailbreak markers no longer match inside longer
  words, so results on the same samples can differ from 0.9.1.
- Documentation wording: `opencomplai docs generate` is named as the gate for
  the high-risk dossier and the pages say that `check` does not validate the
  dossier; the evidence ledger is described as a hash chain, not a Merkle
  tree, in the docs and API summaries; the `verify-log --vault` option says the
  whole log entry is stored in the vault object store; the checker page states
  the golden fixture and shared vector counts it is verified against; and the
  performance page uses the right container image path.

### Fixed

- A `check` over several manifests with `--report-junit`, `--sarif-output` or
  `--summary-md` wrote every system to the same path, so only the last system's
  report survived. Each system now writes `<stem>.<system_id><ext>` beside the
  path you gave; a single-manifest run still writes the exact path.
- A `check` over several manifests with `--sample-set` passed the same file to
  every system, so only the system whose id matched it could pass. Each system
  now gets its own copy with its `system_id` filled in; your file is never
  modified.
- Non-ASCII manifests, tokens and state files no longer fail on Windows hosts
  whose default code page is not UTF-8: the CLI and library now read and write
  these text files as UTF-8.
- An Art. 72 post-market monitoring plan rendered by `recommend` and left
  unedited, or with only its placeholders deleted, was read as authored text.
  The template's own lines no longer count, so the plan now reads Unfilled at
  low confidence instead of Present, and a line that is only a label (such as
  `Owner:`) is not counted as content.
- `opencomplai ai status` counts the files inside nested cache folders (it only
  counted top-level files), shows `<1 MB` for a small cache, shows a model
  whose size is not known as `unknown` instead of `~0 MB`, and says a model
  that has to be downloaded is not yet downloaded when its cache folder exists
  but is empty.

## [0.9.1] — 2026-10-08

### Added

- The Python services (risk-engine, evidence-vault, doc-generator,
  egress-proxy) now log one JSON object per line to standard output (`ts`,
  `level`, `logger`, `service`, `msg`, plus `exc_info`, and `trace_id` inside
  an active OpenTelemetry span), and log errors that their request handlers
  used to swallow. `LOG_LEVEL` sets the level (default `INFO`; an
  unrecognised value falls back to `INFO` with a warning), and the Compose
  stack now passes it to each service. Validation failures caused by client
  input log only the exception class, never the submitted values. Uvicorn's
  own startup and access lines stay plain text. Thanks to @Reh1t (#93).

### Changed

- The adversarial evaluator (`EVAL_ADVERSARIAL_V1`) recognises two more
  refusal-suppression prompts ("never say 'as an AI'", "do not say 'I
  cannot'"), one more compliant-output phrasing and five more refusal
  phrasings ("I'm sorry, but", "I am unable to", ...), so results on the same
  samples can differ from 0.9.0. Thanks to @Reh1t (#91).
- `configure_telemetry()` in `opencomplai-core` now also sets up logging, with
  or without OpenTelemetry installed: it adds the new
  `opencomplai_core.telemetry.JsonFormatter` handler to the root logger (once,
  next to any handlers already there), sets the root level from `LOG_LEVEL`
  (default `INFO`) and keeps `httpx`/`httpcore` at `WARNING` or above, since
  their request lines carry full URLs.

### Fixed

- risk-engine: an override idempotency key containing a space or control
  character no longer breaks the duplicate-override lookup; the key is
  percent-encoded in the request path.

## [0.9.0] — 2026-10-08

### Breaking

Upgrading from 0.8: the [0.9 upgrade guide](https://docs.opencomplai.com/getting-started/upgrading-to-0.9/) lists who each change affects and what to do.

- `opencomplai check --sign` with no signing key (no key file and no
  `SIGNING_KEY_PRIVATE`) now exits 2 before doing anything and writes no
  artifact; it used to write an unsigned one and exit by result. For the old
  behaviour, plus a warning, use the new `--sign-if-available`. The GitHub
  Actions and GitLab CI connectors pass `--sign-if-available` unless
  `SIGNING_KEY_PRIVATE` is set, so keyless CI keeps working. `halt approve`
  follows the same rule. A signing error under `--sign` is now exit 2, not a warning.
- A manifest that contains a `systems` key or is a top-level JSON array is now rejected with exit 2 (one manifest describes one system). Before, `systems` was ignored with a warning.
- Dossiers are no longer HMAC-signed. With only `LOCAL_SIGNING_KEY_PATH` set a
  dossier is now `unsigned` (with a warning) instead of `hmac-local`; only an
  Ed25519 key signs. `opencomplai verify --kind dossier` reports such a dossier as `invalid`
  with code `UNSUPPORTED_SIGNATURE` (exit 1): it cannot be verified, which is not a finding of tampering
  (`CHECKSUM_MISMATCH`, `BAD_SIGNATURE`). Treat older `hmac-local` dossiers as unverifiable.
- The Docker Compose stack now publishes the Prometheus (9090) and Grafana
  (3001) host ports on `127.0.0.1` by default; they used to be reachable
  from other machines. The gateway port is unchanged. If you reach either
  UI from another host, set `OBSERVABILITY_BIND_ADDR=0.0.0.0` in
  `infra/compose/.env` and recreate the containers. Prometheus has no
  authentication and Grafana allows anonymous Viewer access, so read the
  "Network exposure" section of the observability docs first.
- `GET /v1/evidence/ledger-history-tips` no longer builds a tenant's whole
  chain in memory. Called without parameters it behaves as before for
  ledgers of up to 10,000 events and answers `413` above that, with a
  message pointing at the new `limit` (1 to 5000) and `after_seq`
  parameters. With `limit` it returns one page: `genesis`, `tips` for that
  page and `next_after_seq` (`null` on the last page); `after_seq` without
  `limit` is a `422`. The gateway forwards those two parameters (and no
  others). `GET /v1/evidence/verify-chain` now walks the chain in batches
  with constant memory and returns the same result, except that an event
  with a null `seq` now makes it return `false`. `tools/verify-ledger`
  pages through the tips at 5000 per request, so an older copy of the tool
  cannot check a ledger above the 10,000-event cap; it also reports a
  rate-limited gateway (HTTP 429) as such instead of as a connectivity
  error.
- The `opencomplai-ai` base install no longer pulls `transformers` and `onnxruntime`: the deterministic `codebert-onnx` matcher never imported them, and the optional `[onnx]` extra still installs what the Python-API ONNX export needs.
- `SIGNING_KEY_PRIVATE` is now validated as base64 (line wraps and a trailing newline are still
  accepted); a value containing other stray characters raises `SigningKeyError`
  instead of being silently decoded.
- Evidence vault: the `status` of each `GET /v1/portfolio` row changed from `compliant` to `scan_passed`.

### Added

- Docs: eight new concept pages (rule-set versioning, roles and applicability, backlog order, agents, incidents, regimes, high-risk acceptance and published schemas) and a published-schemas index that states the `$id` pattern, the pin and re-pin rules and the observed compatibility practice; the compatibility promise is marked as needing founder review.
- CLI reference pages for `push`, `approve` and `resume`, `keys`, `ai`, `info` and `version`, `deployer-pack` and the multi-manifest portfolio mode of `check`, a row for every `verify` kind in the verify page's Kinds table, and the README group paragraph now names every command group. A test fails when a command or group has no page or nav entry, when a page names an option the command does not have, or when a registered `verify` kind has no row.
- Homebrew formula file under `packaging/homebrew/` with the tap steps; the tap itself is not yet published.
- `opencomplai gaps --map-to DORA|EBA` shows a mapped-only citation per EU AI Act article (human column and a `mapped_regimes` JSON block). Citations, not verdicts: low confidence, flagged for founder review, no statuses or exit codes change, and the default output is unchanged.
- CLI: `opencomplai eval --provider-base-url` points `--provider` at an OpenAI-compatible endpoint (https, or plain http only for localhost); other plain-http hosts and URLs with credentials are rejected before any request is sent.
- `opencomplai check` emits metadata-only oversight, agents, QMS and incident summaries (counts, enums, days and log heads, no free text), signed with the artifact so `push` forwards them unchanged; new options `--oversight-log`, `--agent-log` and `--incident-register`. A source that cannot be read is skipped with a warning.
- CI: `templates/opencomplai.yml` is a GitLab CI/CD component file (inputs for stage, image, version, manifest, extra arguments, SARIF and push); it is not yet published in the GitLab CI/CD Catalog, so include it from a GitLab project that hosts a copy (the guide's `<GITLAB-GROUP>/<PROJECT>` path is a placeholder); `docs/ci/azure-pipelines.yml` is an Azure Pipelines template. Both run `opencomplai check` with `--sign-if-available`, `--report-junit` and `--summary-md`, publish the JUnit result even when the check fails, and fail the job on exit codes 1 to 4; see the new CI for GitLab and Azure guide.
- A bundled prompt-injection seed corpus (`SEED_PROMPT_INJECTION_V1`, 16 short self-authored prompts, prompts only) and `opencomplai eval` without `--sample-set`, which now runs it offline instead of exiting 2. Prompts only, so offline the adversarial evaluator is SKIPPED; with `--provider` the live completions are scored. The corpus is lexical, English only, low confidence and flagged for founder review.
- `opencomplai agents verify-log` checks an agent decision log's chain and signatures, lists entries outside the declared mandate (recomputed from the manifest's agent inventory, never from the log's own flag), and with `--vault` appends one `agent_action` event per entry to the evidence vault; `opencomplai verify --kind agent-log` verifies the same file offline. The mandate-matching rules are a design choice, flagged low confidence for founder review.
- ISO/IEC 42001:2023 as a native framework pack: `--target ISO_IEC_42001` (also `compliance_targets`) assesses 65 clause and Annex A rows, attestation-led (Unverified until a provider attestation is recorded in `framework_inputs`); only four rows (Clause 6.1.2, Clause 6.1.3, A.6.2.7, A.8.2) also look for a matching document, and the worse status wins. Preview data: every row is low confidence and flagged for founder review; nothing certifies ISO conformity. No new `ComplianceTarget` value; EU-only and NIST-only output is unchanged.
- `opencomplai deployer-pack build` seals the Art. 13(3) instructions-for-use JSON into one pack named `deployer_pack_<12 hex>.json` after its own SHA-256, optionally signed (`--sign` exits 2 before writing when no key is available; the same inputs and day give byte-identical bytes). `opencomplai verify --kind deployer-pack` checks it offline and tells an unsigned pack from a tampered one. New vendored `deployer_pack` JSON schema. `check` adds metadata-only `summaries.packs` (hash, date, signer key id, item counts) from `./deployer-pack/` when packs exist there.
- Note: deployer packs are generated offline and never uploaded; only the `summaries.packs` metadata is pushed, never pack text, the system id or any free text.
- GitHub Action `integrations/github-action`: runs `opencomplai check` through a pinned `uvx` call, posts one sticky pull request comment from the Markdown summary, can upload the SARIF verdict, and fails the job with the check exit code. A self-test in the maintainers' CI runs the five `examples/gate-demo` systems through it. Marketplace listing is pending.
- A declared `agent_inventory` is carried verbatim into the Annex IV dossier, on the local path and through the doc-generator service (`opencomplai docs generate` and `check` send it). A manifest without it produces the same dossier bytes and checksum as before. `push` sends only its counts (`summaries.agents`), never the inventory itself.
- README gains a "Who it is for" section and a new guide, `guides/works-alongside.md`, says how OpenComplAI runs beside eval tools, agent-governance toolkits and GRC platforms, what is not built, when an accepted high-risk system exits 0 (only when no other EU AI Act row is Missing), that a preview import of the Agent Governance Toolkit file-sink log exists (`agents import-log`, capped at Partial, no gate effect) and that no bridge to Promptfoo or GRC platforms is built. Statements about other products on guides/works-alongside.md are unverified against those products and need founder review.
- GPAI providers: `opencomplai recommend` now also writes a copyright-policy outline and a training-content summary draft for an Art. 53 row (low confidence, flagged for review).
- `opencomplai docs generate --render md|pdf` also writes the Annex IV dossier as Markdown and/or PDF next to the JSON (local mode). Placeholders and missing items are marked `NOT PROVIDED` and an incomplete dossier carries an `INCOMPLETE` banner; the JSON, checksum and exit codes are unchanged.
- `opencomplai agents attest` signs a statement that a key holder vouches for one agent's mandate hash until an expiry (pinned `agent_attestation/v1` schema, golden vectors for other verifiers). `opencomplai verify --kind agent-attestation` checks it offline (signature, expiry, optionally `--expect mandate_sha256=...` and `--expect now=...`). A verified attestation means a key holder signed that hash, not that the mandate is lawful or complete.
- `opencomplai diff A B` compares two `check --with-gaps` artifacts or gap reports and lists added, removed and changed verdicts plus the rule-set version delta, in human, json or markdown. `--fail-on-regression` exits 1 when any verdict got worse; no new exit code.
- `opencomplai rules changelog [--since V]` prints the rule-set history, oldest first, with each entry's source, confidence and founder-review flag.
- `opencomplai approve` and `resume` append to a signed, hash-chained `oversight-log.json` in the state directory, one entry per approval and per resume, naming the approver's role. `approve --role` is checked against the roles of the manifest's `human_oversight` block (read from `--manifest`, default `system-manifest.json`; a missing file or a manifest without the block behaves as before), and `resume --key` signs the entry (an entry is written unsigned, with a warning, when no key resolves). `opencomplai verify --kind oversight-log` reports edited, deleted or reordered entries as invalid and unsigned entries as unsigned, and prints the chain head and count. Removal of the newest entries is detectable only against a head you stored elsewhere; refused resumes are not logged.
- `opencomplai instructions generate` renders an Art. 13(3) instructions-for-use pack (JSON and Markdown) from the manifest, listing every point the manifest does not capture as not captured. Six new optional manifest fields (`provider_contact`, `foreseeable_misuse`, `input_data_specifications`, `predetermined_changes`, `expected_lifetime_and_maintenance`, `log_interpretation`) are omitted when unset, so existing manifests keep the same bytes. The point list is low-assurance and flagged for founder review.
- GPAI provider pack data: a template for the summary of training content (Art. 53(1)(d)) and a map from the three Code of Practice chapters to the Art. 53 / 55 obligations, with a validator and a docs page. Every row is low confidence and flagged for founder review; nothing is checked against the primary texts, and the code is voluntary with no presumption of conformity.
- SDK `AgentDecisionLog`: a hash-chained, optionally signed log of an agent's decisions that an auditor can verify offline. Raw tool inputs are never stored, only their SHA-256. Detecting truncation needs the head and count stored elsewhere.
- `opencomplai incident` now appends every declare, classify, notify and close to a signed, hash-chained `incident-log.json` (structured fields only, never the free text) and moves the system state on declare and close, writing the log entry first; a refused transition keeps its entry and exits 1. New `opencomplai incident template` renders draft authority-report and downstream-notice templates, flagged as not legally reviewed, and `opencomplai verify --kind incident-log` checks the log.
- `opencomplai incident` (declare, classify, notify, close, status, export) keeps a local incident register and computes notification deadline clocks at read time from an injected clock. The day counts per class are low-confidence data flagged for founder review. New optional `incident_contacts` manifest field, omitted when empty, so existing manifests keep the same bytes.
- Regulatory timeline: `checker` results, `gaps`, `check --with-gaps` and `report` list when each obligation applies, from a new data file that includes the Digital Omnibus dates (Annex III 2027-12-02, Annex I 2028-08-02). Every entry has a source and a confidence and is flagged for founder review; dates not confirmed are shown as "date unconfirmed". Presentation only: JSON output, signed artifacts and the checker engine are unchanged.
- `opencomplai accept` writes a signed high-risk acceptance record bound to the manifest fingerprint under `.opencomplai/acceptances/` for you to commit. `opencomplai check` reads it from the repository (not `~/.opencomplai`) and, when valid, no longer counts `EU_AIA_ART6_HIGH_RISK` as a failure; Missing EU AI Act rows still fail (see Changed) and Art. 5 stays exit 3, and a stale, unsigned or tampered record is reported and ignored. The record embeds its public key, so it proves integrity, not identity: pin signers with `OPENCOMPLAI_TRUSTED_KEY_IDS`. `accept --trap-approval --change-context <context>` writes a trap approval; together with a valid acceptance, a `check` run with the same `--change-context` then no longer exits 4 for that trap or halts the system. What an acceptance statement means is flagged for founder review.
- `opencomplai check` names every recorded operator role (`roles=provider, deployer`; a single role still prints `role=provider`), and articles that do not apply to the recorded session get no control and are counted in one line under `--with-gaps`.
- `opencomplai qms generate --manifest` fills clauses (e), (h) and (i) from the manifest's declared fields without changing any clause status, lists EN 18286 (published, not harmonised) with a cross-check against `harmonised_standards`, and adds a flagged simplified-profile note when `organisation_size` is `micro`. New CLI pages for `qms` and `fria`; the `recommend` page now lists the live templates. The note and the EN 18286 wording are low-confidence, flagged for founder review.
- Optional structured `human_oversight` manifest block (roles, authority, intervention, conditions, training and evidence pointers, escalation). `validate-manifest` rejects duplicate or empty roles and warns when no role can intervene; the Art. 14 gap row reads it as a manifest declaration, PARTIAL at most and never MET. A declared `record_keeping` block now feeds the Art. 12 row the same way.
- The structured `human_oversight` block now appears in Annex IV section 3 of the dossier on the local path and through the doc-generator and gateway. A manifest without the block produces the same dossier bytes and checksum as before, and section 3 counts structured roles toward `provider_supplied` only together with monitoring and incident-response entries.
- A declared agent inventory feeds the Art. 12, 14, 15 and 26 gap rows (decision log reference, approval tools linked to an intervening oversight role, guardrails, mandate). When a scan report is supplied, an agent framework or MCP server the scan detects but the inventory does not declare is reported as a gap; declared-but-undetected items are only listed. Heuristic, PARTIAL at most, never MET; no change without the inventory block.
- `opencomplai agents inventory`, `check` and `report` read the manifest's agent inventory offline (no vault, no network): list the agent tree, validate it and cross-check it against an optional scan report (exit 2 invalid, 1 findings, 0 none; evidence only, never a verdict), and report the inventory with a draft responsibility map that attributes GPAI model duties (Art. 53, 55) to the upstream model provider. Every map row is low confidence and flagged for founder review; the wording is unverified.
- recommend: article-specific templates for Art. 5, 10, 11, 15, 16, 24, 25 and 43.
- A recorded checker session can move articles that do not apply to the system out of the gap report. They are listed under `not_applicable` with the reason and create no controls. Without a session, or when none is recorded, the output is unchanged. This is an operator-role reading flagged for founder review, not a legal determination.
- EU article rows for Art. 26, 49, 72 and 73. The files each row reads are listed under Changed; none of them reads Met.
- The four services and the gateway report the release version (was `0.1.0-dev`), the internal `opencomplai-core` and `opencomplai-cli` floors equal the current version, and the version parity test covers all nine manifests. The gateway version samples in the docs follow.
- `opencomplai check` takes `--report-junit`, `--sarif-output` and `--summary-md` to write a JUnit XML report, SARIF 2.1.0 of the check verdict and the Markdown job summary. Exit codes are unchanged, and a report that cannot be written only warns.
- `opencomplai check -m a.json -m b.json` (repeatable; globs are expanded by the CLI) runs each manifest as its own system and writes `<output-dir>/<system_id>/` plus an unsigned `portfolio-summary.json`. The exit code is the worst child code (4 trap > 3 policy block > 2 validation > 1 control fail > 0). With `--report-junit`, `--sarif-output` or `--summary-md` every system writes to the same path, so only the last system's report is kept (fix planned for 0.9.1).
- `POST /v1/hitl/overrides/{override_id}/second-approval` completes a dual-control override: a distinct second approver sends the first approval's `rationale_hash` and their own rationale, and an `override_second_approved` ledger event is written before it is accepted. The gateway now forwards `requires_dual_approval` on `POST /v1/hitl/overrides`. In API-key mode every caller is the same principal, so two distinct approvers need JWT/OIDC.
- The scanner detects SageMaker, the Databricks SDK, Weights and Biases, Langfuse and Vertex AI. `databricks-sdk` is a general workspace client, so it can flag Databricks use that is not AI (dependency confidence stays capped at 0.7).
- `opencomplai check --output-dir` writes the artifact and sidecars to a chosen directory.
- `opencomplai qms generate --scaffold` writes 13 starter policy files under `docs/qms/` that read as
  Unfilled until completed; existing files are never overwritten.
- Optional `agent_inventory` manifest block (agents, tools, models, mandate, delegation,
  guardrails, logging, responsibility map). `validate-manifest` and `init --section-extras-file`
  deep-check it and exit 2 on a dangling parent, a parent cycle, delegation deeper than
  `max_depth`, a dangling delegate or an unknown `tool:<name>` reference.
- The scanner reads MCP server names from `.mcp.json` / `mcp.json` (MCP_SERVER evidence),
  detects more agent frameworks (langgraph, openai-agents, pydantic-ai, smolagents,
  google-adk, Mastra, litellm, azure-ai-inference), and reports a package listed in two
  signal categories once per category.
- JSON Schemas for the compliance artifact (`scan_status_artifact.schema.json`)
  and the gap report (`gap_report.schema.json`), generated from the models with
  `scripts/generate_artifact_schemas.py` and guarded by a drift test.
- `opencomplai checker --entity-type` can be repeated (a provider that also
  deploys). The checker runs once per role and merges the results; the roles go
  to `operator_roles`, and the obligation ids and one rationale line per role to
  `checker_session`, and the Markdown and JSON exports gain a `Role rationale`
  section. `--write-manifest` on an existing manifest now appends roles instead
  of overwriting it and no longer asks for the system id. Runs without
  `--entity-type` write the same manifest keys as before.
- `opencomplai verify <file>` checks a signed file and reports `verified`,
  `unsigned` (no signature present) or `invalid` (signature does not match).
  It exits 0 only for `verified`; unsigned and invalid both exit 1, and bad
  input (missing file, bad JSON, unknown `--kind`, missing public key) exits 2.
  Kinds: `artifact`, `dossier`, `deployer-pack`, `oversight-log`, `agent-log`, `incident-log` and
  `agent-attestation`.
- `opencomplai verify --kind dossier` verifies an Annex IV dossier: an Ed25519
  signature over the bundle is `verified`, an unsigned dossier is reported
  `unsigned`, and a legacy HMAC-signed, tampered or wrong-key dossier is
  `invalid` with a distinct code (`UNSUPPORTED_SIGNATURE`, `CHECKSUM_MISMATCH`,
  `BAD_SIGNATURE`).
- A key-management page (`docs/src/security/key-management.md`), which `keys
  rotate --help` pointed at under a wrong path; both docstrings now name the
  real path.
- Additive model fields for the 0.9.0 features: `SystemManifest.operator_roles`,
  `organisation_size` and `record_keeping`; `CheckerSessionRef.obligation_ids`
  and `rationale`; `GapReport.not_applicable`; and provenance fields on the
  scan status artifact (`rule_set_version`, `cli_version`, `schema_version`,
  `manifest_sha256`, `timestamp`, `policy_bundle_version`). Every one is left
  out of serialised output while unset, so existing manifests, reports and
  signatures are byte-identical. `opencomplai check` stamps all six on the
  artifact before signing (see the stamping entries below).
- Library only: a shared signed, append-only hash-chain log primitive
  (`opencomplai_core.signed_log`), a `resolve_key` helper that prefers the
  `SIGNING_KEY_PRIVATE` env key and fails loudly when no key exists, and five
  new signing domains (oversight log, agent log, incident log, attestation,
  deployer pack). `approve` and `resume`, `incident`, `agents verify-log`, `agents
  attest` and `deployer-pack build` use them.
- `opencomplai check` now stamps `rule_set_version`, `cli_version`,
  `schema_version` and `manifest_sha256` (SHA-256 of the manifest file, CRLF
  read as LF) on the artifact before signing, so the signature covers them and
  survives `push`.
- GPAI providers: Annex XI and XII documentation template and artifact probes for Art. 53 and 55, active for a recorded GPAI checker session (low confidence, flagged for review).
- `--sort priority` on `gaps`, `report` and `recommend` lists rows by regulatory deadline, then severity, then fix effort (default stays article order, and default output is unchanged). `gaps -o json` gains an ordered top-level `backlog` block only under `--sort priority`; `articles` keep article order. Effort (S/M/L) is a maintainer engineering estimate stored in `template_map.json`, not a compliance claim; deadlines come from the regulatory timeline and rows without one sort last.
- New guide "CI recipes for other systems": Jenkins, Bitbucket Pipelines and CircleCI recipes, exit-code notifications and an artifact-archiving note. The CI guide now uses `opencomplai push` instead of a raw `curl` upload.

### Changed

- Framework wording and the standing line in the README, docs and package READMEs now match the shipped ISO/IEC 42001 pack (native, attestation-led, partial, unreviewed) and the mapped-only DORA and EBA citations.
- Regulatory timeline dates that are still unverified (ninth prohibition, Annex III, Annex I) now show confidence low instead of medium in gaps, check and report output; the gap-source provenance records for the GPAI documentation probes, the adversarial evaluator and the Art. 12 manifest declaration are added, and Art. 26, 49, 72 and 73 map rows read low confidence. No verdict changes.
- The pre-commit hooks now pin `opencomplai-cli` to the revision's own version, and CI exercises them with `pre-commit try-repo`.
- CLI: `agents import-log` reads the JSONL file audit sink of a runtime governance toolkit offline and `agents dispute-report` renders what each agent was told, decided and why for a date window (also from a native agent decision log). The AGT field preset is a low-confidence preview (override with `--map`); imported evidence is labelled "format-valid, not verified", capped at Partial, and has no effect on `check`, `gaps` or exit codes.
- Install scripts `scripts/install.sh` and `scripts/install.ps1` install the CLI with `uv` and a uv-managed Python (3.11 floor), tested in the maintainers' CI on Linux and Windows.
- CLI: `opencomplai init --from-model-card README.md` imports a Hugging Face model card's front matter offline into `training_data_description`, `model_architecture` and `performance_metrics`, recorded as attested (not verified) in the manifest's new `imported_evidence`; explicit flags win and verdicts are unchanged.
- Examples: new `examples/gate-demo/` sandbox with five fictional systems that exit 3, 4, 1, 1 and 0 under `opencomplai check` (prohibited, trap, high-risk, accepted, limited); the README and docs home now point at it instead of the legacy gateway walkthrough in `examples/sample-system/`.
- The GitHub Actions and GitLab CI connectors pass flags to `opencomplai check` (from the command line and from `OPENCOMPLAI_CHECK_ARGS`), and `--commit-ref` defaults to the CI SHA (`GITHUB_SHA` / `CI_COMMIT_SHA`).
- The four OSS API bundles (`api/docs-gen`, `api/egress`, `api/evidence`, `api/risk`) now pin their direct dependencies to the root `uv.lock` versions instead of floors (`vercel-blob` keeps its floor). The next OSS deploy installs these versions.
- Art. 15 now also draws on `EVAL_ADVERSARIAL_V1`: a skipped adversarial evaluator makes an otherwise Met Art. 15 Unverified (worst status wins). A passing run on the bundled seed corpus reads Partial, never Met (heuristic evidence). `EVAL_CALIBRATION_V1` stays deliberately unmapped: it is GPAI opt-in and skipped by default, so mapping it would pin Art. 15 at Unverified for every non-GPAI system. Rule-set 1.6.0 history updated.
- The Art. 13 gap row for an `INSTRUCTIONS.md` or `docs/instructions*` file now checks for Art. 13(3) topic markers (intended purpose or instructions for use, plus oversight, misuse, limitation, accuracy, maintenance or contact): a bare file reads Partial at 0.35 instead of 0.55, one with the markers Partial at 0.6, never Met. Heuristic keywords, low confidence, flagged for founder review; `gaps` output for a bare file changes.
- Art. 12 now reads an event-log file (`oversight-log.json` anywhere in the repository): Partial at most, never Met, and Missing when none is found (it was Unverified), so the gap, check and report goldens moved. `recommend` now writes the Art. 12 template. The probe is low confidence and flagged for founder review.
- `recommend` writes an instructions-for-use checklist (`art13-instructions_for_use.md`) for Art. 13 instead of the Art. 50 disclosure stub. Flagged for founder review.
- `opencomplai check` with a valid acceptance record: Missing EU AI Act rows now fail the check (exit 1, the article ids listed in `failed_controls`; the Art. 6 row is not counted) instead of the Art. 6 failure, and a valid trap approval for the same `--change-context` turns exit 4 into that result without halting the system. Art. 5 stays exit 3 and a stale or invalid record stays exit 1. Behaviour changes only when a record exists. Policy choice flagged for founder review: an acceptance acknowledges the classification and removes no other obligation, which is why Missing rows gate. The CI connectors read the artifact result and inherit this.
- The Art. 11, 26, 49 and 50 gap rows read real files: a `dossier_*.json` (Art. 11), a deployer use log (Art. 26), an EU database registration file (Art. 49) and the Art. 50 disclosure files that `recommend` writes. They show Missing without one and Partial with one, never Met; the Art. 13 notice does not count for Art. 50. Conventions flagged for founder review, not legal tests.
- The gap, report and check golden outputs, the EU AI Act and NIST AI RMF framework `data_version` values and the principles page change for the new article rows.
- Checker content: corrected citations (authorised representative Art. 22, deployer Art. 26), widened the FRIA question and obligation to Annex III 5(b)/5(c) deployers (Annex III systems only), added the Art. 6(4)/49(2) duty for providers relying on the Art. 6(3) derogation, and reworded social scoring in Art. 5 with the ninth prohibition flagged for review.
- The checker version is now `checker-2026-10-05`, and the docs widget, `checker-local.html` and the golden vectors are synced to it. The `needs_founder_review` text comes from the entry above.
- The root `compliance-artifact.json` is no longer tracked.
- `RULE_SET_VERSION` bumped to `1.6.0` and `ruleset_history.json` added.
- The `codebert-onnx` AI backend is now labelled as what it is: a
  deterministic code-signal matcher with fixed confidence values, not a
  CodeBERT model on ONNX Runtime. In `MODEL_CATALOG["codebert-onnx"]`
  (public API of `opencomplai-ai`) the values changed: `display_name` is
  now "Deterministic code-signal matcher (no model)" (was "CodeBERT
  code-signal matcher (deterministic, no download)"), `runtime` is
  `deterministic` (was `onnxruntime`) and `license` is `AGPL-3.0-only`
  (was `MIT`). `ai status` and the interactive `ai configure` picker
  show the new values, and so does any code that reads the catalog. The
  id is unchanged, so existing configs and annotations keep working.
- `ai status` no longer prints a "model not yet downloaded" line for
  `codebert-onnx` or `saas`, which have nothing to download. It shows the
  cache directory, size and files as before, so GGUF models downloaded
  earlier stay visible.
- The docs no longer tell users to install `optimum[onnxruntime]`,
  expect a ~440 MB download, or read `conf` as a cosine similarity; only
  the GGUF models need the `[deep]` extra and a download. The prompt of
  the optional, Python-API-only ONNX export now names the export and says
  scans do not use its output.
- Art. 17(1)(a)-(m) clause files now need content to count. A file with no
  matching keyword in its body, under 8 words of body text, or still holding a
  `_fill in_` placeholder reads `Unfilled` (not `Present`) in `qms generate` and
  `recommend`; `qms generate` adds a Confidence column and `unfilled_count`. The
  whole-article Art. 17 row appends the per-clause counts once any clause file
  exists, and is never `MET`.
- Art. 72 and 73 now read a post-market monitoring plan and a root `incident-log.json`, shown Missing when absent and never Met; two new recommend templates (post-market monitoring plan, serious incident report); the gap, check and report golden outputs are regenerated.
- Internal CI hygiene: third-party GitHub Actions are pinned to full commit SHAs, every workflow declares least-privilege `permissions`, `uv sync` is `--locked`, the actionlint ignores are gone, and new DCO and secret-scan workflows plus a CODEOWNERS file are added. No behaviour change for users.
- `opencomplai serve` page documents the `PROJECT_ROOT` argument, `--host` and `--port`, the loopback-only rule and the
  `serve` extra (thanks to @HarshRajSinghania, public pull request 89).
- `ControlCatalogEntry` gains optional `source`, `confidence` and `needs_founder_review` fields. The evidence freshness windows for Art. 26, 49, 72 and 73 are placeholders and now say so (confidence low, flagged for founder review). Framework-pack rows carry the same fields from their data.
- Node.js 24 LTS replaces Node.js 20, which reached end of life in April 2026: the gateway-api image builds on `node:24-alpine` (pinned by digest), every CI job runs Node 24, and contributors need Node.js 24.

### Removed

- `.github/workflows/compliance-gate.yml.example`: it pointed at an `opencomplai/compliance-action@v1` repository and a gateway script that do not exist. Use `integrations/github-action` instead.

### Fixed

- The doc-generator README no longer says `LOCAL_SIGNING_KEY_PATH` signs dossiers (it signs nothing; dossiers are Ed25519-signed or unsigned) or that `LOG_RETENTION_DAYS` is recorded in the dossier (it is not read), the same claim is corrected in two source docstrings, and a test now scans shipped READMEs, the compose file and source docstrings for these claims.
- Both pre-commit hooks failed to install because `pre-commit` builds the repository root and it could not be built; the root now installs as an empty package, and a test builds it.
- Release workflow and security docs: `publish-pypi.yml` now refuses a tag that differs from the four package versions, runs the wheel smoke test before any upload, generates a CycloneDX SBOM per package (workflow artifact only) and supports a `workflow_dispatch` dry run that publishes nothing. `SECURITY.md`, the supply-chain page and the security guide no longer claim Ed25519-signed releases, `npm audit`, SLSA provenance for wheels or published `1.0.0` images, and a test keeps the claims in step with the workflows.
- `uv tool install opencomplai` and `pipx install opencomplai` now install the `opencomplai` executable; package metadata gains classifiers and project URLs.
- Docs wording corrected: the JS SDK pages say no SDK ships in this release, version samples are version-neutral, the JS/TS scanner coverage is described accurately, and the package READMEs carry the framework standing line.
- `gaps` (several targets) and the HTML report show the NIST AI RMF subcategory text instead of an em dash in the Title column.
- The HTML report's status/text filter now covers every framework table, not only the EU one.
- Removed the unused `_print_human` helper from the CLI.
- Service-mode `check` sends `compliance_targets` and `framework_inputs` to manifest validation, so a bad target set is rejected.
- Model downloads for the AI plugin are now pinned to a commit and verified by sha256, so non-interactive GGUF downloads no longer refuse as unpinned. The phi-3.5-mini download now points at an existing repository (`bartowski/Phi-3.5-mini-instruct-GGUF`; the previous one does not exist).
- A control waived by a manifest exclusion is re-derived once the exclusion is removed; manual waivers are left alone (new `waiver_source` field, vault migration 0010).
- CLI input robustness. `gaps` and `recommend --scan-report` read what `scan -o json` prints
  (the output envelope or a bare report; UTF-8, UTF-8 with BOM, or the UTF-16 a PowerShell 5.1
  redirect writes). `scan`, `gaps` and `check` with `-o json` write one JSON document to stdout
  and send every other line to stderr. A wrongly typed `opencomplai.yaml` value (`scan.fail_on`,
  `scan.framework_detectors`, `scan.allowlisted_categories`, `eval.threshold_overrides`) exits 2
  with a clear message. An unknown key in the manifest warns on stderr, and `--strict` on `gaps`,
  `scan` and `check` makes it exit 2. `check` validates `framework_inputs` and `--baseline`
  before it writes evidence or a halt record, so bad input exits 2 and leaves nothing behind.
- Art. 50 limited-risk pack: machine-readable marking of synthetic output is now cited as `Art.50(2)` (provider duty) and deepfake disclosure as a deployer duty; scan output now cites `Art.50(4), first subparagraph` / `Art.50(4), second subparagraph`. Paragraph and actor are flagged for founder review.
- Artifact probes match real globs, skip `.venv`, `node_modules` and `.git`, and report each
  file once (a risk register found by two patterns is now "1 path(s)").
- The Annex IV dossier no longer claims that logging and the evidence vault are
  enabled and that logs are kept 2555 days for every system. The Article 12
  record-keeping block now holds only what the manifest's `record_keeping`
  block declares: without it, logging and the vault read `false`, no
  `log_retention_days` key appears and `provider_supplied` is `false`;
  `LOG_RETENTION_DAYS` is no longer read. A failed Ed25519 signing attempt now
  warns instead of silently leaving the dossier unsigned.
- A scan finding alone no longer reads `Met` in `opencomplai gaps`. A scan row is
  `Met` only when a mapped finding falls inside the declared Annex III areas;
  `agent_framework`, `mcp_server` and `pii_dataflow` detections (and findings
  with no mapped area) now read `Unverified` ("detected, no compliance
  verdict"), so they no longer make a control `satisfied`.
- `check --sign` signed artifacts survive `opencomplai push`: `check` now
  stamps `timestamp` and `policy_bundle_version` before signing, so push no
  longer changes the signed payload and drops the signature.
- `check` resolves `commit_ref` once (CI commit variable, then `git rev-parse
  HEAD`, else `unresolved`) instead of recording the literal `HEAD`; the
  artifact, `gap_report` and halt record agree.
- `check --sign` and `halt approve` honour `SIGNING_KEY_PRIVATE`; a key file
  is no longer required. An explicit `approve --key` that does not exist still
  exits 2.
- Docs and badge wording corrected to state only what the code does: the
  README and docs no longer claim audit-ready logs, SSO, additional rule
  engines, real-time webhooks or a closed beta; `--scan-mode`, the air-gap
  image recipe and the CI key requirement are described as they behave. The
  badge SVG now reads "OpenComplAI | scan passed".
- The "AI intent skipped" message (and the "opencomplai-ai is not
  installed" error) printed `pip install 'opencomplai-ai'` because Rich
  read `[deep]` as markup and dropped it. They now show
  `pip install 'opencomplai-ai[deep]'`.
- Compliance-artifact.json, scan-report.json and eval-report.json are now written as UTF-8, so Windows readers no longer fail on them.
- QMS clause files written by `qms generate --scaffold` no longer read as Present for Art. 17(1)(k) and (m) when only their `_fill in_` lines were deleted: the scaffold's own prompt questions are ignored when a clause file is checked for content, in `qms generate`, `recommend`, `gaps` and `check`.
- The GitHub Action's sticky pull-request comment, when the summary is over 60000 bytes, is now cut on a character boundary instead of inside a multi-byte character, so the posted comment stays valid UTF-8 and still ends with the truncation note.
- `verify` now exits 2 on an `--expect` key the kind does not use (artifact, dossier and deployer-pack take none), the oversight, incident and agent log kinds check `--expect head=` and `--expect count=` against the recorded anchor, and an empty log is reported `invalid` instead of `verified`, in `verify` and in `agents verify-log`.
- Docs and help: the FAQ, the `gaps` reference and `gaps --help`, the data-model page and the `ComplianceTarget` docstring (and the published dossier JSON schema that copies it) now describe ISO/IEC 42001 as the native `ISO_IEC_42001` pack, attestation-led (partial, unreviewed), instead of mapped only; and `docs.opencomplai.com/cli/` now has a CLI reference index.
- `gaps`, `scan`, `check`, `accept` and the `agents inventory`, `agents check` and `agents report` commands read the manifest as UTF-8, so a manifest with non-ASCII text no longer fails under a Windows code page. `qms generate --manifest` (and its `--scan-report` and `--eval-report` inputs) and the role check of `approve --role` still read files in the locale encoding.
- `sync/verify-sbom.sh` checks the signing identity of the workflow that actually builds the release images (`supply-chain.yml` in `Opencomplai/opencomplai-enterprise`), accepts `<service>:<version>` and expands it to `ghcr.io/opencomplai/opencomplai-enterprise/<service>`, and takes `OPENCOMPLAI_RELEASE_REPO` for images built elsewhere. Verification works only if the GHCR packages are public.

### Security

- Gateway-api transitive dependencies are refreshed so all five service images pass the release vulnerability scan; the scan is recorded in `infra/docker/TRIVY-LAST-RUN.md`.

---

## [0.8.0] — 2026-09-24

### Added

- A system can be assessed against several frameworks side by side. The
  manifest gains `compliance_targets` (framework keys, e.g. `["EU_AI_ACT",
  "NIST_AI_RMF"]`; it takes precedence over `compliance_target`) and
  `framework_inputs`, declarations for frameworks other than the EU AI
  Act: `excluded` maps a requirement id to the reason it does not apply,
  and `attested` maps one to a provider attestation (`statement`,
  `attested_by`, `attested_at`) where the framework accepts one (neither
  framework in this release does). Both keys are left out of a manifest
  that does not set them, so existing manifests serialise unchanged. The
  EU AI Act is evaluated natively; NIST AI RMF 1.0 is derived from its
  evidence through the crosswalk. Reports for frameworks other than the
  EU AI Act carry a framework-neutral disclaimer, and their rows can have
  the new `attestation` and `crosswalk` sources and the `attested`
  confidence label.
- `opencomplai gaps` and `opencomplai check --with-gaps` assess every target
  framework: `--target` can be repeated, and without it the manifest's
  `compliance_targets` (else `compliance_target`) are used. With exactly one
  `EU_AI_ACT` or `NIST_AI_RMF` target the output is unchanged; for any other
  set `gaps` prints one table per framework and `gaps --output json` adds a
  `frameworks` block (one report per target) under the framework-neutral
  disclaimer. `check --with-gaps` attaches `nist_rmf_report` whenever
  `NIST_AI_RMF` is a target.
- `ScanStatusArtifact.framework_reports`: for any target set other than
  exactly `EU_AI_ACT` or exactly `NIST_AI_RMF`, `check --with-gaps` embeds
  one framework report per target, and `report` renders them from the
  artifact. The key is omitted when unset, so other artifacts keep their
  bytes and signatures; `gap_report` and `nist_rmf_report` are written as
  before.
- Controls, `recommend` and `report` cover natively evaluated frameworks
  other than the EU AI Act (none ships in this release; see the guide to
  adding framework packs). `gaps` and `check --with-gaps` sync their
  requirements to the control register (ids prefixed `<FW>:`; requirements
  excluded in `framework_inputs` become waived controls with the
  justification as the waiver rationale), and the control catalog takes
  their titles and TTLs from the framework's requirements map. `controls
  status --framework` (repeatable) picks the frameworks counted; the default
  is `EU_AI_ACT`, so the status line and exit code are unchanged.
  `recommend` writes `generic_requirement.md` for such rows that have no
  template of their own, and `report --gap-report` renders one section per
  framework other than the EU AI Act from a multi-framework `gaps --output
  json` file. NIST AI RMF, derived from EU AI Act evidence, adds no controls
  or fixes of its own.
- Opt-in CI gating for frameworks other than the EU AI Act:
  `opencomplai.yaml` `gate: {frameworks, fail_on}` or `check --gate FW`
  (repeatable, replaces the file's list) and `--gate-fail-on
  missing|partial`. A Missing (or, with `partial`, Partial) row of a gated
  framework appends its prefixed id to `failed_controls` and turns `PASS`
  into `CONTROL_FAIL` (exit 1); other results are unchanged. Excluded,
  Unverified and Met rows never fail. A bad gate exits 2 before anything is
  written. `controls status` also counts gated frameworks by default, `gaps`
  notes the gate under a gated framework's table, and the GitHub Actions and
  GitLab CI connectors summarise gated ids as `<FW>: N requirement(s)`.
  Without a gate, output is unchanged.
- `POST /v1/manifests/validate` (gateway and risk engine) accepts
  `compliance_targets` and `framework_inputs` and validates the manifest with
  the core `SystemManifest` model; an empty list or an unknown framework id
  is a 422. The gateway OpenAPI spec and REST reference describe
  `compliance_target` as legacy and mark `/v1/risk/classify`,
  `/v1/docs/generate` and `/v1/checker/*` as EU AI Act only.
- The `opencomplai` SDK and `opencomplai_core` export `evaluate_targets`,
  `resolve_targets`, `FRAMEWORKS`, `FrameworkPack`, `FrameworkReport` and
  `GapReport`, for assessing several frameworks from Python.
- Docs: a Frameworks section (what is evaluated, derived or only mapped, how
  to target several frameworks, exclusions, attestations and gating) and a
  guide to adding framework packs.

### Changed

- `opencomplai gaps` without `--target` now follows the manifest: a manifest
  whose `compliance_target` is `NIST_AI_RMF` gets the NIST AI RMF table, where
  it used to get the EU AI Act table.
- `opencomplai validate-manifest` rejects an unknown framework key in
  `compliance_targets` (exit 2), as `gaps` and `check` do, and lists the
  targets in its human output.
- `opencomplai check` (and `gaps`, `controls status`) now reads
  `opencomplai.yaml` for `gate`, from `--repo-root` (`controls status`:
  the current directory). A malformed file (not valid YAML, a section that
  is not a mapping, or a `gate.frameworks` that is not a list) exits 2
  where `check` used to ignore it.
- Package descriptions, the README and the docs site no longer describe
  Opencomplai as EU AI Act only: the EU AI Act is evaluated natively and NIST
  AI RMF 1.0 is derived from the same evidence.
- `opencomplai-cli` now requires `opencomplai-core>=0.8.0`, and the
  `opencomplai` meta-package requires `opencomplai-core` and
  `opencomplai-cli` `>=0.8.0`.
- `scripts/smoke_wheel_install.sh` also runs `check --with-gaps` on an EU AI
  Act plus NIST AI RMF manifest, asserting `framework_reports`,
  `gap_report` and `nist_rmf_report`, and a `check --gate NIST_AI_RMF`
  that must fail.

### Removed

- **Breaking for SDK callers:** `bridge_to_manifest_fields()` no longer
  returns the `intended_purpose` key deprecated in 0.7.1; read the tier
  label from `checker_verdict`.

### Fixed

- `opencomplai scan` exits 2 with an error on a malformed `opencomplai.yaml`
  (not valid YAML, or a file or `scan`/`eval` section that is not a
  mapping) instead of crashing with a traceback and exit 1.
- Rule rationales list matched keywords in a stable (sorted) order; they
  used to change order from run to run.

---

## [0.7.1] — 2026-09-23

### Added

- `scripts/smoke_wheel_install.sh` builds the `opencomplai-core`,
  `opencomplai-cli` and `opencomplai` wheels the way the PyPI release does,
  installs them into a clean venv and runs `--version`, `init`, `check
  --with-gaps` and an offline `docs generate`, so a module or data file the
  wheels fail to ship is caught before a pip user hits it.

### Changed

- `bridge_to_manifest_fields()` returns the checker's tier label as
  `checker_verdict`; its `intended_purpose` key is deprecated and will be
  removed in 0.8.0.
- `opencomplai-cli` now requires `opencomplai-core>=0.7.1`, and the
  `opencomplai` meta-package requires `opencomplai-core` and
  `opencomplai-cli` `>=0.7.1`, so `pip install -U opencomplai` picks up
  these fixes.

### Fixed

- `opencomplai checker --write-manifest` no longer writes the checker's tier
  label (`prohibited_practice`, `high_risk_ai_system`, ...) into
  `intended_purpose`; it asks for the real purpose (or takes
  `--intended-purpose`) and records the verdict in
  `checker_session.verdict`. `init --interactive` no longer pre-fills the
  purpose with the label. `check` honours the verdict: `prohibited_practice`
  fails with `POLICY_BLOCK` (exit 3), `high_risk_ai_system` with at least
  `CONTROL_FAIL` (exit 1), where 0.7.0 could return `PASS`. Manifests written
  by 0.7.0 are recognised by the tier label in `intended_purpose` and gated
  the same way, with a warning to replace it. **CI using such a manifest may
  start failing; that is the fix.**
- `check --sign` signed the artifact before `--scan --fail-on` and
  `--with-gaps` changed it, so `compliance-artifact.json` did not verify
  against `signing.pub`. It is now signed once, after its last change; in
  service mode the ledger entry also records the final signed artifact
  rather than the draft.
- `check --with-gaps` now runs the documentation/code probes against
  `--repo-root` (default: the current directory), like `gaps`, so the
  artifact-backed rows that were always `unverified` can become `partial` or
  `missing`.
- A code-scan discrepancy (a finding mapping to an Annex III area the
  manifest does not declare) marks the article `missing` for every signal
  category, not only biometric, so Art. 6 and Art. 10 rows can newly become
  `missing`.
- `recommend --gap-report` and `report --gap-report` accept `gaps --output
  json` output (the envelope, not only a bare gap report), including UTF-16
  files from a PowerShell redirect and ANSI code-page files from cmd.exe.
- `docs generate` without `OPENCOMPLAI_API_URL` works from a PyPI install; it
  failed with "No module named 'opencomplai_doc_generator'". The Annex IV
  generator moved into `opencomplai-core` as
  `opencomplai_core.dossier_generator`.
- `opencomplai push` of a 0.7.0 artifact is no longer rejected by the hosted
  dashboard with `SCHEMA_VIOLATION` (fixed server-side).
- Transparency obligations cite Art. 50 (they cited Art. 52, their number in
  the Commission proposal); the `ComplianceTarget` description no longer
  says NIST AI RMF is only mapped, and the Annex IV dossier JSON Schema is
  regenerated to match. `exit-codes.md` now describes `TRAP_DETECTED` and
  exit 3 correctly.

---

## [0.7.0] — 2026-09-19

### Added

- `opencomplai fria generate`: drafts an Art. 27 fundamental-rights impact
  assessment from the system manifest, the checker's `r5_fria` answers when
  present, and the control register, in Markdown and JSON.
- `opencomplai qms generate`: renders an Art. 17(1)(a)-(m) quality-management
  document with per-clause evidence status (present/missing/partial), reusing
  the same 13-clause probes `opencomplai recommend`/`gaps` already report.
- Art. 27 (fundamental rights impact assessment) and per-clause Art. 17
  tracking join the control register, gap reporting, and `opencomplai
  recommend` (previously Art. 17 was tracked only at the whole-article level).
- NIST AI RMF 1.0 is now an **evaluated** compliance target:
  `opencomplai gaps --target NIST_AI_RMF` and `opencomplai check` emit a
  verdict per RMF subcategory, deterministically re-projected from existing
  EU AI Act evidence via a new framework crosswalk — no new scanner or
  evaluator was added. Coverage is partial today (the `MANAGE` function has
  no crosswalk rows yet); see `docs/concepts/nist-ai-rmf.md`.
- A machine-readable EU AI Act ↔ ISO/IEC 42001:2023 ↔ NIST AI RMF 1.0
  framework crosswalk; `opencomplai gaps`'s output gains a "Mapped" column
  citing the ISO/IEC 42001 clause per article. `compliance_target` is now a
  proper enum (`EU_AI_ACT` | `NIST_AI_RMF`) instead of a free string.
- A harmonised-standards catalogue for Annex IV Section 7, validated against
  Section 7 entries (warns on an unmatched entry, never a hard fail).
- `docs/src/getting-started/deployment-journey.md`: one canonical
  install → init → check → CI gate → dashboard → pre-commit → self-hosted
  deployment sequence, replacing several partially-overlapping pages.
- Annex IV Section 8 gains `declaration_sha256`, populated when a signed
  declaration of conformity is uploaded as evidence, so the reference can be
  verified against the attached document without embedding it in the dossier.
- A generated, versioned JSON Schema for the Annex IV dossier
  (`data/annex_iv_dossier.schema.json`), with a drift test.
- `opencomplai` SDK ships a PEP 561 `py.typed` marker (also added to
  `opencomplai_core`, the package that actually defines the re-exported
  types) and re-exports `RiskLevel`, `RuleResult`, and `ScanResult` from
  `opencomplai_core.models`, so SDK consumers no longer need to reach into
  the core package for result inspection and enum checks (#80).

### Changed

- **Breaking for CI pipelines that ignore exit codes:** `docs generate` and
  the doc-generator service now refuse an invalid HIGH-risk Annex IV dossier
  by default (exit 2 / HTTP 422) instead of always succeeding — existing CI
  pipelines that relied on always-zero-exit must add `--allow-incomplete`
  (CLI) or `allow_incomplete: true` (service) to keep the old behaviour. The
  invalid dossier is still written/persisted either way, so an auditor can
  see what failed.
- Annex IV `provider_supplied` fields (Sections 4, 6, 7, 9) now require real
  structure — a dated entry, a recognised harmonised standard, or
  non-placeholder attestation text — instead of accepting any non-empty
  string.
- `RULE_SET_VERSION` bumped to `1.5.0` (the Art. 27 gap-mapping addition is a
  rule-set change under Annex IV traceability).
- `docs/src/guides/ci-integration.md` now leads with the OSS-native path
  (install → manifest → `opencomplai check` as a CI step); the hosted
  dashboard's `/connect` step is now an explicitly optional callout. The
  guide's CI YAML is vendored into `docs/ci/` so it's byte-pinned and
  testable without the enterprise checkout.
- README's Quick Start is trimmed to install + init + check + a link to the
  new deployment-journey page; the pre-commit hook's pinned tag now matches
  the actual latest release instead of a stale `v0.4.0`.
- `docs/src/contributing/release-process.md` rewritten to describe the real
  four-package (`core`/`cli`/`ai`/`sdk-python`), Trusted-Publishing-based
  release process — it previously described a single pre-1.0 package never
  published to PyPI.
- README documents `.ocignore`: how scan-time file exclusion differs from
  `.gitignore`, first-scan bootstrap, and the `--no-ocignore-bootstrap` /
  `--ocignore PATH` flags on `opencomplai scan` (#81).

### Fixed

- `docs/src/getting-started/quick-start.md` no longer claims the CLI has no
  `--version` flag (it has had one, plus `version`/`info` subcommands, for
  several releases).
- `docs/src/guides/ci-integration.md`'s manifest filename is now consistent
  (`system-manifest.json` everywhere; it previously also said `manifest.yaml`
  in one place).
- README no longer promises a GitHub/GitLab composite `action.yml` that
  doesn't exist — it points at the copy-paste workflow YAML instead.
- All previously-orphaned documentation pages (the API reference, several
  CLI/concepts/guides pages, and the new deployment-journey page) are now
  linked from the docs navigation; the stale, unused repo-root `mkdocs.yml`
  is removed.
- egress-proxy's Docker HEALTHCHECK now probes its own `/egress-health`
  liveness endpoint instead of the gateway-proxied `/health`, matching
  docker-compose and gateway-api's probe path (closes #73, #82).

### Security

- anyio is floored at 4.14.2, closing CVE-2026-63374, CVE-2026-63349 and
  CVE-2026-64847 that pip-audit flagged against 4.14.1 (dev/services
  dependency only — the published wheels do not depend on it).

Thanks to [@anvitha1633](https://github.com/anvitha1633) for the
[#82](https://github.com/Opencomplai/opencomplai/pull/82) contribution
(issue #73). Thanks to [@DYNOSuprovo](https://github.com/DYNOSuprovo) for
the [#80](https://github.com/Opencomplai/opencomplai/pull/80) contribution
(issue #78). Thanks to
[@HarshRajSinghania](https://github.com/HarshRajSinghania) for the
[#81](https://github.com/Opencomplai/opencomplai/pull/81) contribution
(issue #59).

---

## [0.6.0] — 2026-09-04

### Added

- `docs generate --push` and `push --kind {scan-status,dossier-envelope}`: a
  dossier-envelope producer for the dashboard's ingest pipeline, sharing the
  scan-status pair's commit resolution, redirect-blocking opener, and env
  contract (`OPENCOMPLAI_PUSH_DOSSIER=1` opts in the CI connectors).
  Pushing the same envelope twice replays by content hash.
- CLI documentation now matches what the commands actually do: the README
  covers `push` and `docs generate --push` with a real self-serve quick
  start, `enroll` is hidden until a bootstrap-token UI exists, `withdraw
  --local-only` skips the always-401 remote call explicitly, and the CI
  integration guide is pinned byte-for-byte to `docs/ci/*.yml` by test.
- Shared EU AI Act checker golden vectors — 24 cases covering prohibited
  practices, Annex I/III high-risk, each Art. 6(3) derogation, profiling
  override, out-of-scope, and every entity type — asserted against both the
  OSS engine and the vendored dashboard checker.

### Changed

- ruff is pinned to 0.15.12 for both uv and pre-commit, which had drifted
  to different versions; the pin came with a one-time autofix and format
  pass (#52).
- README badges are now live instead of committed SVGs (#51).

### Security

- cryptography and pillow are floored at 50.0.0 and 12.3.0, closing the
  padding-oracle and image-parsing advisories pip-audit flagged (#53).
- The Python dependency audit also runs weekly, so newly published
  advisories are caught between pushes.
- Dependabot now watches the uv lockfile, npm workspaces, and GitHub
  Actions.
- The transformers advisories are deferred behind the optimum-onnx cap
  that holds it at 4.57.x; tracked in Opencomplai/opencomplai#54.

---

## [0.5.0] — 2026-08-26

### Added

- Per-tenant ledger sequencing and a hash chain that commits to the payload's
  prefix (migrations `0008`, `0009`), closing gaps in cross-tenant isolation
  and chain-tamper detection (community contribution, [#49](https://github.com/Opencomplai/opencomplai/pull/49), issues #46/#47).
- `opencomplai-gha-connector` / `opencomplai-gitlab-connector` console
  scripts are now actually registered, so the CI integration commands the
  docs reference work after `pip install` instead of failing with "command
  not found".
- Vercel gateway adapter type-checking and end-to-end adapter tests
  (mount-prefix rewrite + handler).

### Fixed

- The AI classifier no longer crashes on non-finite (`NaN`/`Infinity`)
  `annex_iii_area` or timeout values, which previously escaped validation
  and silently wiped every AI finding for the scan.
- The SaaS backend's subject-gating now matches the local backend's
  narrower `art6_3_profiling`-clearing behavior instead of clearing it on
  every null `annex_iii_area`.
- The CLI no longer routes the zero-setup codebert-onnx backend through the
  optional ONNX-export path, which prompted for a ~440 MB download (or
  silently disabled `--ai-intent` in CI).
- `NATURAL_PERSON_CUES` no longer subject-gates migration/asylum use cases
  out of Annex III 7(b) due to an untokenizable compound cue
  (`asylum_seeker` → `asylum`, `refugee`).
- Evidence vault: `get_tenant_session`'s restricted role no longer leaks
  onto the pooled connection after COMMIT.
- The Vercel adapter now strips the mount prefix correctly so adapter
  requests reach real routes.
- `packages/cli/src/opencomplai_cli/data/checker-local.html` is committed
  so a fresh clone can actually install: `packages/cli/pyproject.toml`
  force-includes it in the wheel, but it was previously untracked.

Thanks to [@HasanAlHalabi](https://github.com/HasanAlHalabi) for the
[#49](https://github.com/Opencomplai/opencomplai/pull/49) contribution
(issues #45–#48).

---

## [0.4.0] — 2026-08-20

### Added

- Persistent control-instance register: `ControlInstance` model, control
  catalog, and deterministic identity (`control_id = sha256(tenant_id |
  system_id | obligation_id)`, idempotent across runs). Instances derive from
  a `gaps` run and persist to the evidence vault (migration `0007`,
  tenant-scoped RLS). New `opencomplai controls` command group (`list`,
  `assign`, `attach-evidence`, `status`) gives a CI-consumable summary of
  what's satisfied, missing, stale, or waived.
- Evidence provenance and freshness metadata on evidence objects; read-time
  freshness detection and change-triggered reassessment
  (`opencomplai_risk_engine.control_reassessment`) — no new scheduler, no
  cron service.
- Annex IV provider-attestation fields on `SystemManifest`. `docs generate`
  now loads the most recent scan/eval artifacts from disk and wires them into
  dossier generation instead of leaving those sections dead, and stops
  fabricating Section 3 content the provider never supplied — absence stays
  an explicit placeholder, never a guess.
- First-class Art. 17 (QMS) gap probe and a content-aware Art. 9 (risk
  register) probe.
- HITL halt/resume state machine wired into `check` and `docs generate`: new
  top-level `approve`/`resume` commands and exit code `4`
  (`HALTED_PENDING_REVIEW`).
- `compliance-artifact.json` gains an optional top-level `controls` block
  (summary counts + per-control rows) — additive, existing consumers are
  unaffected.
- Annex IV coverage ledger and controls-lifecycle docs
  (`docs/src/concepts/annex-iv-coverage.md`, `docs/src/concepts/controls.md`).
- `CONTRIBUTORS.md`, and a `Maintainers` section in `README.md` and
  `CONTRIBUTING.md`.

### Fixed

- The CLI no longer aborts with `UnicodeEncodeError` on a Windows console
  left on a legacy code page (cp437/cp1252, the default OEM code page);
  output degrades to ASCII instead of crashing mid-render (community
  contribution, `packages/cli/src/opencomplai_cli/_encoding.py`).
- Installation and quick-start docs no longer hardcode a stale PyPI version
  or claim the CLI has no `--version` flag; `opencomplai scan --quick`
  examples no longer show a trailing positional path argument the CLI
  doesn't accept (community contributions).

### Changed

- README: corrected the SDK package name (`opencomplai`, not
  `opencomplai-sdk`), softened the "Closed Beta Pilot" framing now that the
  quick-scan and EU AI Act Checker paths are free with zero setup, and
  swapped the broken CI (Node) badge — it linked to a workflow this repo
  doesn't run — for a PyPI version badge.

---

## [0.3.0] — 2026-08-13

### Added

- Fail-closed scanner defaults: refuse symlinks, numeric file/byte caps, report
  text sanitize helpers, and `scan_errors` gating when `--fail-on` is set.
- Versioned CLI JSON `ScanOutputEnvelope` for scan/gaps/report (not a signed
  `ScanStatusArtifact`).
- Artifact probes for Arts. 9, 13, 14, 16, 24, 43 plus honesty/confidence labels
  on gap rows; MCP/agent detector (`DET_AGENTS_MCP_V1`).
- Four compile-checked Python remediation templates (transparency, logging,
  oversight, disclosure helpers) via `opencomplai recommend`.
- Working Inspect-AI eval bridge MVP: curated `strong_reject` / `bbq` /
  `bigbench_calibration` pin, `--log-dir`, never gates `check`.
- Local `opencomplai serve` (optional `[serve]` extra) — loopback dashboard.
- Meta-package extras re-export: `reports`, `inspect-bridge`, `serve`.
- Docs: serve, Inspect-AI eval bridge, hostile-scan defaults, SOC2/ISO control mapping,
  ADR local-serve-vs-saas.

### Changed

- Interactive HTML reports embed the JSON envelope and support status/text filters.
- **Breaking:** Inspect-AI eval bridge hard-cut rename — `--suite inspect-ai`,
  pip extra `inspect-bridge`, module `opencomplai_core.bridges.inspect_eval`,
  evaluator IDs `EVAL_INSPECT_*` (evidence hashes change). Previous suite/extra
  identifiers removed with no aliases.
- **Breaking (signatures):** every Ed25519 signature is now domain-separated —
  the signed bytes are `opencomplai.sig.v1\0<purpose>\0<payload>`. One keypair
  signs scan-status artifacts, Annex IV dossier bundles and compliance badges,
  and nothing in the signed bytes said which was which: a signature from
  `opencomplai check --sign` verified unmodified as a compliance-badge
  signature for the same object. `sign_bundle_bytes`/`verify_bundle_bytes` now
  take a required `domain`. **Signatures produced before this change do not
  verify, deliberately and with no compatibility flag** — nothing in the system
  re-verifies a stored signature, so an accept-both window would only have kept
  the confusion alive. Re-sign anything you need to verify again.
- **Breaking (badges):** issuing a badge now requires a signature whenever
  `OSS_BADGE_PUBLIC_KEY_PATH` is set. Previously an unsigned request skipped
  verification entirely even with the key configured. With no key configured,
  unsigned issuance is unchanged — that is OSS unsigned mode.

### Removed

- `EvidenceObject.encryption_profile` and the `evidence_objects`
  `encryption_profile` column (evidence-vault migration `0006`). It advertised
  `"AES-256-GCM"`, including in the generated OpenAPI, while no CAS backend has
  ever encrypted anything; nothing wrote it and nothing read it. Evidence
  objects are stored as plaintext — integrity comes from content-hash
  re-verification on read, confidentiality from volume- or bucket-level
  encryption at the deployment layer.

---

## [0.1.2] — 2026-07-11 — First PyPI release

### Added

- `opencomplai`, `opencomplai-cli`, `opencomplai-core`, and `opencomplai-ai` are now
  published to PyPI. `pip install opencomplai` resolves the full stack; no source
  checkout required. Packages are built and published in dependency order from
  the `opencomplai-enterprise` release workflow (PyPI's Trusted Publisher is
  registered against that repo); this repository's own CI (`ci-python.yml`)
  covers lint/test only.

### Contract

- The stable API contract introduced in `0.1.0` (exit codes `0`–`4`, the
  `compliance-artifact.json` / `ScanStatusArtifact` schema) is unchanged by the PyPI
  release — publishing changes distribution only, not behavior.

---

## [0.1.0] — 2026-06-28 — Initial public release

### Added

- Risk classification engine for the EU AI Act with a deterministic, rule-based core:
  `UnacceptableRiskRule`, `AnnexIIIClassifierRule`, `ProfilingDetectionRule`, and
  `SubstantialModificationRule`.
- `opencomplai` CLI: `init`, `check`, `checker`, `verify-output`, `docs generate`,
  `sync metadata`, `risk classify`, `validate-manifest`, and `dashboard` commands.
- Interactive EU AI Act checker — a browser-based wizard for scope, high-risk
  classification, GPAI, and obligations, available on the docs site and offline via
  `opencomplai checker --local`.
- Gateway API routes: `/v1/sync/metadata`, `/v1/docs/generate`, `/v1/verify/claims`,
  `/v1/evidence/events`, `/v1/risk/classify`, and `/v1/manifests/validate`.
- Evidence vault: append-only, Merkle-linked ledger with a `LedgerEvent` chain and a
  `/v1/evidence/verify-chain` endpoint.
- Docker Compose stack: gateway-api, risk-engine, evidence-vault, doc-generator,
  egress-proxy, Prometheus, Grafana, PostgreSQL, and Redis.
- Egress proxy: `EGRESS_ALLOWED_DESTINATIONS` allowlist enforcement; fail-closed by
  default (air-gap ready).
- Release signing: Ed25519 keypair generation in `~/.opencomplai/`; `--sign` flag for
  `opencomplai check`.
- Python SDK: `ScanStatusArtifact`, `SystemManifest`, `RiskResult`, `AssessmentInput`,
  and `ModelMetadata` exported from `opencomplai`.
- Developer documentation site (`docs.opencomplai.com`) covering the CLI, SDK,
  deployment, concepts, architecture, contributing, and troubleshooting.
- Supply-chain tooling: SBOM generation (`scripts/verify-sbom.sh`).

### Contract

- `opencomplai check` writes `compliance-artifact.json` (a `ScanStatusArtifact`), which is
  the canonical CI gate output.
- Exit codes are contractual: `0` = PASS, `1` = CONTROL_FAIL, `2` = VALIDATION_FAIL,
  `3` = POLICY_BLOCK, `4` = TRAP_DETECTED.

---

`opencomplai`, `opencomplai-cli`, `opencomplai-core`, and `opencomplai-ai` are published
on PyPI:

```bash
pip install opencomplai
```

Installing from a source checkout remains supported for contributors:

```bash
git clone https://github.com/Opencomplai/opencomplai
cd opencomplai
pip install -e packages/core -e packages/cli -e packages/sdk-python
```

See [Contributing — Release Process](docs/src/contributing/release-process.md) for the
release/publish workflow.

[0.11.0]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.11.0
[0.10.0]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.10.0
[0.9.2]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.9.2
[0.9.1]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.9.1
[0.9.0]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.9.0
[0.8.0]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.8.0
[0.7.1]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.7.1
[0.3.0]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.3.0
[0.1.2]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.1.2
[0.1.0]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.1.0
