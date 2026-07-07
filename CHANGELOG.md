# Changelog

All notable changes to Opencomplai are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this
project follows [Semantic Versioning](https://semver.org/).

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

This project is pre-release. The packages are not yet published to PyPI. Install from
source:

```bash
git clone https://github.com/Opencomplai/opencomplai
cd opencomplai
pip install -e packages/core -e packages/cli -e packages/sdk-python
```

The v0.1 release will publish `opencomplai`, `opencomplai-cli`, and `opencomplai-core` to
PyPI with a stable API contract. See
[Contributing — Release Process](docs/src/contributing/release-process.md) for details.

[0.1.0]: https://github.com/Opencomplai/opencomplai/releases/tag/v0.1.0
