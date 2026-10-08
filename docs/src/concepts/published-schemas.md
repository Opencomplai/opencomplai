# Published schemas

Opencomplai writes several JSON files that other programs read: the signed scan artifact, the gap report,
the Annex IV dossier, the deployer pack, agent attestations, and the payloads a dashboard accepts. Each has
a JSON Schema (draft 2020-12). This page lists every schema, who writes it and who reads it, and states how
the schemas are versioned.

Paths under `dashboard-saas/` exist in the enterprise repository only and are written as code spans, not
links.

## Index

The schemas under `packages/core/src/opencomplai_core/data/` ship with the CLI. The ones under
`dashboard-saas/schemas/` are vendored by the dashboard and pinned (see [Pin and re-pin
rules](#pin-and-re-pin-rules)).

| File | `$id` | Owner and source | Producer | Consumer | Status |
|---|---|---|---|---|---|
| `scan_status_artifact.schema.json` | `https://schemas.opencomplai.dev/scan_status_artifact/v1` | Core. Generated from the `ScanStatusArtifact` model by `scripts/generate_artifact_schemas.py`. | `opencomplai check` | Anyone validating `compliance-artifact.json` | Published, v1. |
| `gap_report.schema.json` | `https://schemas.opencomplai.dev/gap_report/v1` | Core. Generated from the `GapReport` model by the same script. | `opencomplai gaps --output json`, `check --with-gaps` | `opencomplai diff`, report tooling | Published, v1. |
| `annex_iv_dossier.schema.json` | none yet | Core. Generated from the `AnnexIVDossier` model by `scripts/generate_dossier_schema.py`. | `opencomplai docs generate` | Auditors and CI that validate a dossier | Published, no `$id`. A drift test keeps it in step with the model. |
| `deployer_pack.schema.json` | `https://schemas.opencomplai.dev/deployer_pack/v1` | Core. Generated from the `DeployerPack` model. | `opencomplai deployer-pack build` | `opencomplai verify --kind deployer-pack` | Published, v1. |
| `agent_attestation_v1.schema.json` | none; the document fixes `schema_version` to `agent_attestation/v1` | Core. Mirrors the signed attestation record. | `opencomplai agents attest` | `opencomplai verify --kind agent-attestation` | Published, versioned by its file name and `schema_version`. |
| `first_scan_status.schema.json` | `https://schemas.opencomplai.dev/first_scan_status/v1` | Dashboard, vendored. Source: the PRD's section on the status artifact. | `opencomplai push` (maps a scan artifact onto it) | Dashboard ingest, `POST /v1/ingest/scan-status` | Published, v1. The effective allowlist of what the dashboard may store. |
| `dossier_envelope.schema.json` | `https://schemas.opencomplai.dev/dossier_envelope/v1` | Dashboard, vendored. Mirrors the metadata fields of `AnnexIVDossier`. | The CLI's publish module, from a dossier made by `opencomplai docs generate` | Dashboard ingest, `POST /v1/ingest/dossier-envelope` | Published, v1. Carries metadata only; the dossier bundle never crosses the boundary. |
| `metrics_payload.schema.json` | `https://schemas.opencomplai.dev/metrics_payload/v1` | Dashboard, vendored. Source: the egress allowlist. | Clients that send aggregated metrics | Dashboard ingest, `POST /v1/ingest/metrics` | Published, v1. Every field comes from the allowlist. |
| `error_envelope.schema.json` | `https://schemas.opencomplai.dev/error_envelope/v1` | Dashboard, vendored. Mirrors the gateway's `ErrorEnvelope`. | Dashboard API error responses | API clients | Published, v1. |
| `deployer_pack.schema.json` (vendored copy) | `https://schemas.opencomplai.dev/deployer_pack/v1` | Dashboard, vendored copy of the core file; a test keeps the two equal. | `opencomplai deployer-pack build` | Not an ingest kind: packs are generated offline and never uploaded | Vendored copy, same `$id` as the core file. |

Other files in `dashboard-saas/schemas/` are not JSON Schemas but are part of the pinned set:

| File | What it is |
|---|---|
| `PIN.json` | The pinned source commit, the date, a note on each re-pin, and the list of vendored files with their sources. |
| `MANIFEST.sha256` | A SHA-256 per file in the directory, for every file except itself. |
| `CHANGELOG.md` | One row per `PIN.json` bump: date, previous and new SHA, reason, reviewer. |
| `allowed_fields.json` | The egress allowlist of fields. |
| `checker_golden_vectors.json` | Shared test vectors for the applicability checker, asserted from both the core and the dashboard suites. |
| `signature_spec.md` | How the artifact signature is canonicalised. |

## Versioning policy

### $id pattern

A published schema's `$id` is `https://schemas.opencomplai.dev/<name>/v<major>`, where `<name>` is the
file name without `.schema.json` and `<major>` is a single integer. The artifact also carries a
`schema_version` string that matches the major (`1`); it lives in the schema document, not on the model, so
it never changes signed bytes. The host is an identifier, not a promise that the URL resolves.

A schema without an `$id` (the dossier, the attestation) is identified by its file name until one is added.
Adding an `$id` to the dossier schema must not reuse the dashboard's `first_scan_status` name.

### Pin and re-pin rules

The dashboard never edits a vendored schema by hand. It re-pins:

1. Edit the schema, in core first when the source is a model, and regenerate it.
2. Update `PIN.json`: the pinned commit SHA, the date and the note. A commit cannot name its own SHA, so the
   new SHA is the parent of the commit that widens the schema together with the model.
3. Add a row to `CHANGELOG.md` for the bump.
4. Run `python dashboard-saas/scripts/schema_drift_check.py --regen` last, to rewrite `MANIFEST.sha256`.

`dashboard-saas/scripts/schema_drift_check.py --verify` fails the build when any file in the directory changed without a new
manifest, or when `PIN.json` names a commit that has no changelog row. The changelog file is itself hashed,
so touching it without the re-pin fails the same gate. Adding a vendored file that is not an ingest kind
needs a changelog row but leaves the pinned SHA and the ingest contract unchanged.

The ingest schema's `summaries` block follows one more rule. It is a single optional object with five
closed sub-objects (`oversight`, `agents`, `qms`, `incidents`, `packs`) made of leaf values only: integers,
booleans, enumerations, SHA-256 hashes and dates matched by a `pattern`, with bounded string lengths and
capped arrays. It has no free text and no open object. A guard test in the ingest service walks the schema
definitions and fails if a later widening adds one. Nothing is added to the egress allowlist for it.

### Compatibility promise

!!! warning "Needs founder review"
    This section describes what has been done so far. It is not yet a reviewed public commitment.

Observed practice, from the changelog's rows so far:

- Changes to a published schema have been **additive**: a new optional property, a wider enumeration, a new
  optional block.
- `additionalProperties: false` has been kept, so a field the schema does not name is still rejected.
- The required fields and the minimum length of `commit_ref` have not changed.
- A change that would remove or rename a field, make an optional field required, narrow a type, or open a
  closed object would be a new major version with a new `$id`.

Because of the closed shape, a producer that writes a newer optional field to a dashboard still on an older
pin is rejected. The changelog records a re-pin made for that reason.
