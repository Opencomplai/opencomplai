# ADR: Local serve vs SaaS; eval bridge never gates `check`

**Status:** Accepted  
**Date:** 2026-07-16

## Context

OpenComplAI has two dashboard surfaces that must not be confused:

1. **Local developer UX** — optional `opencomplai serve` (CLI `[serve]` extra)
2. **Pro / `dashboard-saas`** — multi-tenant ingest of signed metadata only

Separately, the optional Inspect-AI eval bridge must never feed
`opencomplai check` exit codes (determinism and air-gap moat).

## Decision

1. Local `serve` binds to `127.0.0.1` only, stores history under XDG paths, and
   must not hold SaaS tokens or call ingest APIs.
2. `eval.gate_on_bridge` defaults to **false** forever. Bridge results may attach
   to eval reports / dossiers only via explicit opt-in workflows outside `check`.
3. Default wheels and default compose images exclude `inspect-ai`, FastAPI serve
   deps, and WeasyPrint.

## Consequences

- Competitive local dashboard parity without collapsing into Pro SaaS.
- Auditors can rely on contractual exit codes 0–4 for `check` without Inspect
  variance.
- Documentation must state clearly that CLI JSON envelopes are not signed
  `ScanStatusArtifact` outputs.
