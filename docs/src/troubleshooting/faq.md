# FAQ

## General

### What is Opencomplai?

Opencomplai is an open-source EU AI Act compliance toolkit for AI engineering teams. It classifies risk, generates evidence, and gates CI/CD pipelines — not a document processing or upload platform.

### Which version of the EU AI Act does Opencomplai implement?

The rule engine implements the EU AI Act as published in the Official Journal of the EU (2024). The compliance target is `EU_AI_ACT` (default). Future targets (NIST AI RMF, ISO/IEC 42001) are on the roadmap.

### Is Opencomplai a legal compliance guarantee?

No. Opencomplai automates the technical checks in the EU AI Act obligations but does not constitute legal advice or a formal conformity assessment. Engage a qualified Notified Body for formal certification of high-risk systems.

---

## Installation

### Can I install without Docker?

Yes. The CLI and SDK work in fully local mode:

=== "macOS / Linux"
    ```bash
    pip install opencomplai
    opencomplai init --system-id my-system --intended-purpose "..."
    opencomplai check  # uses local rule engine, no Docker needed
    ```

=== "Windows (PowerShell)"
    ```powershell
    pip install opencomplai
    opencomplai init --system-id my-system --intended-purpose "..."
    opencomplai check  # uses local rule engine, no Docker needed
    ```

Docker is only required to run the full service stack (gateway API, evidence vault, doc generator).

### Is the package published to PyPI?

The SDK is currently pre-release (`0.1.0-dev`). If `pip install opencomplai` fails with a "not found" error, install from source:

=== "macOS / Linux"
    ```bash
    git clone https://github.com/Opencomplai/opencomplai
    cd opencomplai
    uv pip install -e packages/sdk-python
    uv pip install -e packages/cli
    ```

=== "Windows (PowerShell)"
    ```powershell
    git clone https://github.com/Opencomplai/opencomplai
    cd opencomplai
    uv pip install -e packages/sdk-python
    uv pip install -e packages/cli
    ```

### What Python version is required?

Python 3.11 or newer.

---

## CLI

### What does `opencomplai init` actually create?

Two things:

1. **`~/.opencomplai/`** — created on first run, contains an Ed25519 signing keypair (`signing.key`, `signing.pub`) and `config.yaml` (install_id, gateway_url).
2. **`system-manifest.json`** (or the path from `--output`) — a `SystemManifest` JSON describing your AI system.

### Do I need to run `init` every time?

No. Run `init` once per system. Subsequent `check` runs read the existing manifest. If the manifest already exists and you run `init` again, it overwrites the manifest but does not regenerate the signing keypair.

### How do I check without Docker Compose?

Don't set `OPENCOMPLAI_API_URL`. The CLI falls back to the local rule engine automatically:

=== "macOS / Linux"
    ```bash
    opencomplai check   # local mode, no network needed
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check   # local mode, no network needed
    ```

### What is `compliance-artifact.json`?

The `ScanStatusArtifact` written to the current directory after every `check` run. This is the machine-readable CI gate artifact. It contains `install_id`, `system_id`, `commit_ref`, `result`, `failed_controls`, `evidence_hashes`, `rationale_hash`, `duration_ms`, and optionally a signature. Consume it in CI to gate on `result`.

### How do I gate a CI pipeline on the result?

=== "macOS / Linux"
    ```bash
    opencomplai check --scan-mode ci
    # The exit code is the gate:
    # 0 = pass, 1 = control_fail, 2 = validation_fail, 3 = policy_block, 4 = trap_detected
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check --scan-mode ci
    # The exit code is the gate:
    # 0 = pass, 1 = control_fail, 2 = validation_fail, 3 = policy_block, 4 = trap_detected
    ```

Any non-zero exit code will fail the CI step.

---

## Risk classification

### My system shows `control_fail` but I think it should pass. What do I do?

1. Run `opencomplai check --output json` and inspect `failed_controls`.
2. Read the `rationale` for each failed rule in the `RiskResult` (available via `opencomplai risk classify --system-id ... --output json`).
3. If the rule requires additional information (e.g. `chatbot_disclosure: true`), provide it in `AssessmentInput.answers` when calling via the SDK, or update `system-manifest.json` accordingly.

### What is `high_risk_presumption`?

Setting `--high-risk-presumption` in `opencomplai init` tells the engine to classify the system as `high` risk regardless of its `intended_purpose`. Use this if you are provisionally presuming high risk while awaiting a formal Annex III determination.

### What triggers `TRAP_DETECTED`?

The `SubstantialModificationRule` (`EU_AIA_ART25_MODIFICATION_TRAP`) triggers when the system detects signals consistent with a substantial post-market modification as described in EU AI Act Article 25. This requires re-assessment. See the rule implementation in `packages/core/src/opencomplai_core/rules.py`.

---

## Docker Compose stack

### Which services are included in the stack?

| Service | Port | Purpose |
|---|---|---|
| `gateway-api` | 8080 (default) | Main API entry point |
| `risk-engine` | internal | Risk classification and rule evaluation |
| `evidence-vault` | internal | Append-only Merkle ledger + CAS |
| `doc-generator` | internal | Annex IV dossier generation |
| `egress-proxy` | internal | Outbound allowlist enforcement |
| `postgres` | internal | Persistent store |
| `redis` | internal | Task queues |
| `prometheus` | 9090 | Metrics scraping |
| `grafana` | 3000/3001 | Dashboards |

### How do I reset the database?

=== "macOS / Linux"
    ```bash
    docker compose -f infra/compose/docker-compose.yml down -v
    # -v removes named volumes including the PostgreSQL data volume
    docker compose -f infra/compose/docker-compose.yml up -d
    ```

=== "Windows (PowerShell)"
    ```powershell
    docker compose -f infra/compose/docker-compose.yml down -v
    # -v removes named volumes including the PostgreSQL data volume
    docker compose -f infra/compose/docker-compose.yml up -d
    ```

---

## Security

### Does Opencomplai send any data externally?

In local mode (no `OPENCOMPLAI_API_URL`): no network calls are made. In Docker Compose mode with `EGRESS_ALLOWED_DESTINATIONS=` (the default): all outbound egress is blocked by the egress-proxy. Data only leaves the Docker network if you explicitly set `EGRESS_ALLOWED_DESTINATIONS` to a dashboard endpoint and enroll via `opencomplai dashboard enroll`.

### What data does the dashboard sync?

Only fields on the `ALLOWED_FIELDS` allowlist: metadata identifiers, result codes, control counts, timing, and hashes. No model weights, training data, raw evidence, or PII ever leave the egress proxy.
