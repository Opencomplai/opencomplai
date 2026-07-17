# Product control mapping — gap closure (SOC 2 / ISO 27001)

This note maps lean gap-closure features to Trust Services Criteria and
ISO/IEC 27001:2022 Annex A controls. It is **product design evidence**, not a
CPA attestation or certified ISMS Statement of Applicability.

## Scope assumption

- SOC 2: Security (CC) + Confidentiality (C1) + Processing Integrity (PI1)
- ISO 27001:2022 Annex A themes that touch the OpenComplAI system boundary

## Mapping

| Feature | SOC 2 | ISO 27001:2022 | Evidence |
|---------|-------|----------------|----------|
| Symlink refuse + byte caps + sanitize | CC5/CC6/CC7 | A.8.28, A.8.9 | scanner defaults, hostile fixtures |
| `scan_errors` + fail-on gating | CC7, PI1 | A.8.16 | envelope fields, CLI fail-on |
| Import isolation (`check` vs bridge/serve) | CC8, PI1 | A.8.9 | `test_check_import_isolation.py` |
| Opt-in extras (Inspect / serve) | CC6, CC9 | A.5.19–A.5.22 | pyproject extras, install docs |
| Local serve loopback-only | CC6 | A.5.15 | TrustedHost, host allowlist |
| SaaS ingest allowlist unchanged | C1 | A.5.14, A.5.23 | `allowed_fields.json` boundary |
| Envelope ≠ signed artifact | PI1, C1 | A.5.33 | docs + `ScanOutputEnvelope` |
| AGPL template disclaimer | CC2 | A.5.31, A.5.32 | template banners + recommend docs |
| Inspect-AI eval bridge never gates `check` | PI1 | A.8.9 | ADR + `gate_on_bridge: false` |

## Explicit non-claims

Org-level CC1–CC4 governance, annual access reviews, and IR tabletops remain
ISMS program items outside this feature delivery.
