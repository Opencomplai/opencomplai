# ADR: Framework Packs — Assessing One System Against Several Frameworks

**Status:** Accepted (amended 2026-10, 2026-11, 2026-11b)  
Amended in the 0.9.0 round (SU-GM2, E-13) and the 0.14.0 round (FWMAP).  
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
   evidence via the crosswalk); `ISO_IEC_42001` (native, `data/iso_42001.json`) joins
   them (see the 2026-10 amendment). A test-only `FIXTURE` native pack, registered per
   test, proves the generic path.
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
9. **Legacy runs are frozen per data version.** A run whose resolved targets are exactly
   `["EU_AI_ACT"]` or `["NIST_AI_RMF"]` produces the same output byte for byte while the
   framework `data_version` and the rule-set version are unchanged, pinned by golden
   snapshots. A deliberate data commit (new articles, sources or crosswalk rows) changes
   the `data_version` and regenerates the goldens once, with a reviewed diff.
   `gap_report` and `nist_rmf_report` are always written as today and kept permanently;
   `framework_reports` is added only for other target sets.
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

## Amendment 2026-10 (E-13)

ISO/IEC 42001 is now a native pack: registry key `ISO_IEC_42001`, data in
`data/iso_42001.json`, `DISCLAIMER_V2`. Rows are attestation-led: a provider's recorded
attestation is the evidence, so a row reads Unverified until one exists. Only four rows
also reference an existing probe (`risk_register` for Clause 6.1.2 and 6.1.3,
`deployer_instructions` for A.8.2, `provider_qms_bundle` for A.6.2.7), and the worst
status wins, so a file alone never makes them Met. Every row carries `source`, low
`confidence` and `needs_founder_review: true`; titles are short headings, not standard
text. `ComplianceTarget` gets no member, so the Annex IV dossier schema stays stable.
DORA and EBA stay mapped-only, in a separate data file owned by SU-32b and SU-32c.

## Amendment 2026-11 (FWMAP)

1. **NIST AI RMF maps per subcategory.** Each entry of
   `data/nist_ai_rmf_subcategories.json` lists the EU AI Act articles (`eu_ai_act`, each
   with a confidence) whose evidence is re-projected onto it, replacing the
   category-level lookup through `data/framework_crosswalk.json`. Worst status and lowest
   confidence still win. The NIST pack's `data_files` no longer include the crosswalk.
   This is a deliberate data change under decision 9: the NIST golden snapshots were
   regenerated once, and the EU snapshots did not change.
2. **Derived packs may take attestations.** `FrameworkPack.derive` receives the pack's
   attestations, and an optional `attestable` callable names the ids that accept one.
   For NIST AI RMF these are the subcategories with an empty `eu_ai_act` list; an
   attested one reads Met with source `attestation`, in both `nist_rmf_report` and
   `framework_reports`. A subcategory that has EU AI Act evidence takes no attestation.
3. **ISO/IEC 27090 is a native pack.** Registry key `ISO_IEC_27090`, data in
   `data/iso_27090.json`, `DISCLAIMER_V2`. Its 31 rows are the guidance clauses of
   ISO/IEC 27090:2026 that ask for something, each with its table-of-contents heading and
   a one-line note in the project's own words. Every row takes an attestation; four also
   take an output evaluator, and eight a supporting probe (point 7). It is guidance, so
   the label says it certifies nothing.
4. **Cross-framework links are data.** NIST entries carry `iso_42001` and `iso_27090`
   id lists; ISO/IEC 42001 and ISO/IEC 27090 rows carry `eu_ai_act`, `nist_ai_rmf` and the
   other ISO list; ISO/IEC 27090 rows also carry `iso_27001` (Annex A ids) and `soc2`
   (Trust Services Criteria ids). The links compute no verdict. NIST-to-42001 links come from NIST's
   published crosswalk; the rest are the project's own, at low confidence. A test keeps
   both directions in agreement, and `docs/src/frameworks/mappings.md` is generated from
   them.
5. **`framework_crosswalk.json` stays as it is.** It still feeds the EU `Mapped` column,
   the control catalog and the dossier, so it remains a category-level summary.
6. **Scoping is data.** `FrameworkInputs` takes an optional `scope` of three yes/no
   answers (`trains_models`, `uses_retrieval`, `public_api`; unanswered is
   `None`), left out of the serialised manifest when unset. A native row may carry
   `scope_out`, a list of groups of answer keys; when every answer in any one group is
   `false`, `evaluate_targets` moves the row to `excluded` with a generated reason that
   names the answers. An explicit `excluded` entry keeps its own reason, and a row with
   an attestation stays in the report. A `scope` for a framework with no `scope_out` rows
   does nothing. ISO/IEC 27090 carries `scope_out` on nine rows. `scope_out` is part of the
   pack's data, so `data_version` of ISO/IEC 27090 changed once; no golden pins it.
7. **Supporting evidence.** An `artifact` source may carry `"role": "supporting"`. A
   plain artifact source cannot sit on an attestation-led row: an artifact probe never
   reads Met, so attested plus a file found would read Partial and attested plus no file
   would read Missing. A supporting source is resolved after the row's other sources and
   never lowers the row:
    - If the other sources resolve to Met (an attestation, a passing evaluator), the row
      stays Met with the same source, `evidence_ref` and label; the file it found is
      named in the rationale. `evidence_ref` is left alone because control derivation
      binds it into the control's evidence references, and a string that changes with
      the repository would pile up stale ones.
    - If they resolve to Unverified (nothing attested) and the probe found evidence, the
      row stays Unverified: source `artifact`, `evidence_ref` the file, and a rationale
      that says evidence was found in that file, that it is not attested, and how to
      record an attestation (the other source's text). Finding a file is not a verdict,
      and Unverified never fails a gate, so a threat model in the repository cannot
      break CI.
    - A probe that finds nothing, finds only a file without its content markers, or has no
      `--repo-root` changes nothing.
    - Missing and Partial from the other sources are untouched, so a failing evaluator
      still reads Missing.

   Evidence means a matched path, or code hint, whose content markers hold. Each supporting
   probe runs once per report. The conformance test accepts the role only on `artifact`
   sources, with a known probe ref and next to at least one source without the role.
   The EU AI Act map has none, so its output is unchanged.
8. **ISO/IEC 27090 supporting probes.** Eight rows gain a supporting probe, each a
   file-name or code convention with content markers:
   `ai_supply_chain_pins` (5.5, B.3: an SBOM header, a hash pin as in `dvc.lock` or a
   lock file for models and datasets, or a hub model pinned to a commit hash),
   `rate_limiting_config` (6.5, 7.8, B.2: a rate-limit library import or an nginx or
   Envoy directive), `ai_threat_model` (5.6: a threat-model document naming an
   AI-specific attack), `ai_red_team_report` (5.7: a red-team report naming one, with a
   test-result marker) and the existing `event_log_evidence` (7.5). Known limits: any
   valid SBOM counts, whether or not it lists models; only Python code is read for
   pinned hub revisions; dependency lock files are not read (nearly every repository has
   one); and a hub revision of `main` or a tag is not a pin. Row 6.2 stays attestation
   only: no convention records a provenance *check*, and a datasheet only states where
   data came from. Probe wording is flagged for founder review like every other probe.

## Amendment 2026-11b (FWMAP wave 2)

1. **Eleven more native packs.** `ISO_IEC_27001`, `SOC_2`, `NIS2`, `DORA`, `EBA`, `EIOPA_AI`,
   `GDPR`, `CRA`, `ETSI_EN_304_223`, `ISO_IEC_42005` and `ISO_IEC_23894` are registered from one table
   in `frameworks.py`, each with its own data file and the label suffix "attestation-led, not an audit,
   certification or legal assessment". No engine change: they use the native-pack path of decision 1.
2. **Forward links only.** Rows carry `eu_ai_act`, and `iso_27001` (Annex A ids) or `iso_42001` (row
   ids) where relevant. Reverse views are computed by `scripts/generate_framework_mappings_doc.py`; no
   reverse lists are written into the older packs, so their `data_version` does not move.
3. **Mapped-only citations stay.** `mapped_regimes.json` and `gaps --map-to DORA|EBA` are unchanged;
   the DORA and EBA packs sit beside them.
4. **Not in `ComplianceTarget`.** As decision 2 requires.

## Out of scope

Colorado and other framework packs; a document registry; per-framework
vault columns.
