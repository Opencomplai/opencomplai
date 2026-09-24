# ADR: Framework Packs — Assessing One System Against Several Frameworks

**Status:** Accepted  
**Date:** 2026-09-23

## Context

A manifest names one `compliance_target`. `gaps` and `check` evaluate the EU AI Act
natively; `NIST_AI_RMF` is a re-projection of that EU evidence through
`data/framework_crosswalk.json` (`nist_rmf_report.py`). There is no way to see several
frameworks side by side, to record that a requirement does not apply, or to record a
provider's statement that one is met. Existing EU and NIST users, their CI gates and
their signed artifacts must not notice the change.

## Decision

1. **Registry, not plugins.** `frameworks.py` holds a frozen `FrameworkPack` dataclass
   (`id`, `label`, `disclaimer_ref`, `requirements`, `derive`, `data_files`) and a plain
   `FRAMEWORKS` dict. No ABCs, entry points or loaders. The 0.8.0 registry has
   `EU_AI_ACT` (native, `data/gap_article_map.json`) and `NIST_AI_RMF` (derived from EU
   evidence via the crosswalk). A test-only `FIXTURE` native pack, registered per test,
   proves the generic path; no other frameworks ship in this round.
2. **Targets are registry keys.** `SystemManifest.compliance_targets: list[str] | None`
   lists the frameworks to assess. Resolution: `check`/`gaps` flags replace the
   manifest; else `compliance_targets`; else `[compliance_target]`. Unknown keys are an
   error. `ComplianceTarget` gets no new members, so the Annex IV dossier schema, which
   embeds it, stays stable.
3. **Requirement ids carry their framework.** EU ids stay unprefixed (`"Art. 9"`);
   every other id is `"<FW>:<id>"` (`"NIST_AI_RMF:GOVERN 1.1"`). The framework is read
   from the prefix, never stored as a new column. Controls reuse `derive_controls` and
   `make_control_id` unchanged, so control ids of different frameworks cannot collide.
4. **Native pack data format.** A requirements map is
   `{"<FW>:<id>": {"title", "default_ttl_days", "sources": [{"kind", "ref"}]}}` with
   kinds `artifact`, `attestation`, `scan` and `evaluator`; `rule` and `obligation`
   stay EU-only. Artifact refs must be existing probe names. An `attestation` source's
   `ref` is its own requirement id, the key used in `framework_inputs.<FW>.attested`.
   `gap_article_map.json` is not changed. `data_version` is the first 12 hex digits of
   a SHA-256 over the parsed JSON of the pack's data files dumped with sorted keys, so
   it ignores line endings and key order.
5. **Declarations live in the manifest.** `SystemManifest.framework_inputs` maps a
   framework to `FrameworkInputs(excluded, attested)`: requirement id to exclusion
   reason, and requirement id to `Attestation(statement, attested_by, attested_at)`.
   Both reject unknown keys and empty strings. The manifest is the only place for
   compliance declarations; `opencomplai.yaml` configures tool behaviour only.
6. **Unset means absent.** A wrap `model_serializer` drops `compliance_targets` and
   `framework_inputs` from `SystemManifest` output when unset, so a manifest that never
   used them serialises to exactly the bytes it did before.
7. **Honest labels.** New `ArticleGapSource.ATTESTATION` / `CROSSWALK` and
   `ConfidenceLabel.ATTESTED` say where a verdict came from. `DISCLAIMER_V2` is
   framework-neutral; the EU AI Act keeps `DISCLAIMER_V1`. The CLI JSON envelope takes
   the disclaimer as a parameter, defaulting to V1.
8. **Additive artifact block.** Each assessed framework becomes a `FrameworkReport`
   (`framework`, `label`, `data_version`, `derived_from`, `disclaimer_ref`, `gated`,
   `excluded`, `report: GapReport`); `GapReport` itself is unchanged.
   `ScanStatusArtifact.framework_reports` is omitted from serialisation when `None`, so
   existing artifacts keep their bytes and signatures.
9. **Legacy runs are frozen.** A run whose resolved targets are exactly `["EU_AI_ACT"]`
   or `["NIST_AI_RMF"]` produces today's output byte for byte, pinned by golden
   snapshots. `gap_report` and `nist_rmf_report` are always written as today and kept
   permanently; `framework_reports` is added only for other target sets.
10. **Gating is opt-in.** `opencomplai.yaml` `gate: {frameworks: [...], fail_on:
    missing|partial}` (default `missing`), or `check --gate FW` (repeatable, replaces
    the file's list) and `--gate-fail-on`. A row of a gated framework fails when it is
    Missing (or Missing/Partial with `fail_on: partial`) after exclusions;
    Unverified and Met never fail. Failing prefixed ids are appended to
    `failed_controls` after the EU ids, and the only result change is `PASS` to
    `CONTROL_FAIL` (exit 1); every other result is left as it is. Gating runs after the
    existing halt wiring. The EU AI Act cannot be listed (it already gates), and an
    unknown framework, a framework that is not a target or a bad `fail_on` exits 2
    before anything is written. `controls status` defaults to the EU AI Act plus the
    gated frameworks.

## Consequences

- Adding a native framework is a data file plus one registry entry and tests.
- NIST verdicts stay a re-projection of EU evidence and say so (`derived_from`,
  `CROSSWALK`); they never claim independent evaluation.
- Attested rows are only as good as the provider's statement; `ATTESTED` keeps that
  visible to anyone reading the report.
- New enum values reach JSON consumers only when a multi-framework run emits them.

## Out of scope

ISO/IEC 42001, Colorado and other framework packs; a document registry; per-framework
vault columns.
