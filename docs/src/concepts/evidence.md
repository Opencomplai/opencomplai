# Evidence

Every compliance check produces evidence objects that can be audited independently of the Opencomplai platform.

## What Opencomplai considers evidence

| Evidence type | Where it is stored | How it is referenced |
|---|---|---|
| `RiskResult` JSON | Local: `compliance-artifact.json`. Service mode: evidence-vault CAS. | `evidence_hashes[]` in `ScanStatusArtifact` |
| Per-rule rationale | Embedded in `RiskResult.rule_results[].rationale` | `rationale_hash` (SHA-256) in `ScanStatusArtifact` |
| Ledger events | PostgreSQL + append-only log in evidence-vault | `event_id` UUIDs |

## Content-addressed storage (CAS)

In service-backed mode (Docker Compose stack), evidence objects are stored in the `evidence-vault` service using a content-addressed model: each object's SHA-256 hash is its storage key. This means evidence objects are immutable — the same hash always refers to the same content.

## The Merkle ledger

The evidence-vault service maintains an append-only Merkle-linked event ledger. Each `LedgerEvent` records:

- `event_id` — UUID
- `ts` — timestamp
- `event_type` — e.g. `compliance_check_started`, `compliance_check_completed`
- `payload_hash` — SHA-256 of the event payload
- `prev_hash` — SHA-256 of the previous event (creating the chain)

The ledger chain can be independently verified with `tools/verify-ledger/verify_ledger.py`.

## Verifying the ledger

=== "macOS / Linux"
    ```bash
    python3 tools/verify-ledger/verify_ledger.py \
      --gateway-url http://localhost:8080
    ```

=== "Windows (PowerShell)"
    ```powershell
    python tools\verify-ledger\verify_ledger.py --gateway-url http://localhost:8080
    ```

Expected output on a valid chain:

```text
[INFO]  Checking ledger integrity at: http://localhost:8080/v1/evidence/verify-chain
[PASS]  Evidence ledger chain is valid — no tampering detected
```

## In local (non-service) mode

When `OPENCOMPLAI_API_URL` is not set, `compliance-artifact.json` is the sole evidence output. `evidence_hashes` will be empty in local mode.

## Scanner signal categories and detectors

Code-corroboration scan evidence (`opencomplai scan`) is tagged with a `SignalCategory`
and produced by a versioned `detector_id`, so evidence stays traceable to the exact
detection logic that produced it:

| Signal category | Detector(s) | Notes |
|---|---|---|
| `AGENT_FRAMEWORK` | `DET_FRAMEWORK_AST_V1` | Opt-in (`--framework-detectors`). AST-level: fires on framework object *construction + invocation* (LangChain, CrewAI, AutoGen, LangGraph), not just a lexical import. See [scan reference](../cli/scan.md#framework-object-detection---framework-detectors). |

Other signal categories (AI SDK usage, ML frameworks, vector/embedding stores, PII
dataflow, biometric, scoring/profiling) are produced by the existing lexical detectors
and are always-on (no opt-in flag).
