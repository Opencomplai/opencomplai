# Changelog

All notable changes to Opencomplai are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this
project follows [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

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
- CodeQL analysis runs on Python and TypeScript.
- The transformers advisories are deferred behind the optimum-onnx cap
  that holds it at 4.57.x; tracked in #54.

### Fixed

- The Node CI workflow never actually started: `pnpm/action-setup` was
  missing from the Actions allowlist (#50).

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

[0.3.0]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.3.0
[0.1.2]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.1.2
[0.1.0]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.1.0
