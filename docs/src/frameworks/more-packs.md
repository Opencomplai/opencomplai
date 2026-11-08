# More framework packs

Besides the EU AI Act, NIST AI RMF, ISO/IEC 42001 and ISO/IEC 27090, Opencomplai carries eleven more
frameworks as native, attestation-led packs. They work like ISO/IEC 42001: one row per requirement,
article, control or criterion; every row takes a provider attestation and reads **Unverified** until you
record one. A few rows also look for supporting evidence in the repository, which never lowers a row and
never makes an unattested row Met.

None of this is an audit, a certification, a SOC 2 report or a legal assessment. Every row is the
project's own short description at low confidence, flagged for founder review. For copyrighted standards
(ISO, AICPA, ETSI) the rows carry ids and headings only, never the standard's text.

## The packs

| Framework | Key | Rows | Source the ids follow | Supporting evidence |
|---|---|---|---|---|
| ISO/IEC 27001:2022 (incl. Amd 1:2024) | `ISO_IEC_27001` | 118: clauses 4.1-10.2 and the 93 Annex A controls | Contents lists of ISO/IEC 27001:2022 and ISO/IEC 27002:2022 | SBOM or model pins (A.5.21); event logs (A.8.15, A.8.16) |
| SOC 2 Trust Services Criteria (2017, points of focus revised 2022) | `SOC_2` | 61: CC1-CC9, A1, C1, PI1, P1-P8 | Criterion ids as AICPA numbers them, checked against public outlines | event logs (CC7.2) |
| NIS2, Directive (EU) 2022/2555 | `NIS2` | 21: Arts 20, 21 and 23 | The Directive; ISO/IEC 27001 links mostly from ENISA's NIS2 technical implementation guidance mapping | none |
| DORA, Regulation (EU) 2022/2554 | `DORA` | 37: Arts 5-14, 16-19, 24-30, 45 | The Regulation as published | event logs (Art. 10); red-team report (Arts 24, 25) |
| EBA guidelines | `EBA` | 25: GL/2019/04 (3.8), GL/2019/02 (outsourcing), GL/2020/06 (loan origination) | The guidelines; GL/2019/04 as amended by GL/2025/02 | none |
| EIOPA Opinion on AI governance and risk management (Aug 2025) | `EIOPA_AI` | 8 topics | The Opinion's own paragraph ranges | none |
| GDPR, Regulation (EU) 2016/679 | `GDPR` | 21 articles that matter for an AI system | The Regulation as published | none |
| Cyber Resilience Act, Regulation (EU) 2024/2847 | `CRA` | 63: Art. 13, 14, 28, 30 and Annexes I, II, VII | The Regulation as published | SBOM or pins (Annex I Part II (1)); threat model (Art. 13(2)) |
| ETSI EN 304 223 V2.1.1 (2025-12) | `ETSI_EN_304_223` | 72 provisions under 13 principles | The EN's provision numbers | red-team report, threat model, SBOM or pins on the matching provisions |
| ISO/IEC 42005:2025 (AI system impact assessment) | `ISO_IEC_42005` | 20 clauses | Contents list of the published standard | none |
| ISO/IEC 23894:2023 (AI risk management guidance) | `ISO_IEC_23894` | 23 clauses | Contents list of the published standard | none |

Every row lists the EU AI Act articles it relates to. The security and operational frameworks also list
ISO/IEC 27001 Annex A controls, and ISO/IEC 42005 and ISO/IEC 23894 list ISO/IEC 42001 rows. Links are
the project's own judgement unless the table names an official mapping. See
[Framework mappings](mappings.md) for every row and link, including which frameworks point at each
ISO/IEC 27001 control.

## Using a pack

Target it like any other framework and record attestations under `framework_inputs`:

```json
{
  "compliance_targets": ["EU_AI_ACT", "GDPR", "ISO_IEC_27001"],
  "framework_inputs": {
    "GDPR": {
      "attested": {
        "GDPR:Art. 35": {
          "statement": "DPIA for the support assistant approved; see records/dpia-2026.pdf.",
          "attested_by": "Jane Doe",
          "attested_at": "2026-11-03"
        }
      }
    }
  }
}
```

`opencomplai gaps --target GDPR` prints the table; `check --with-gaps` writes it into `framework_reports`;
`check --gate GDPR` gates CI on its Missing rows. An Unverified row fails a gate only if you ask for it
(see [Failing a build on unattested rows](#failing-a-build-on-unattested-rows)). A row that does
not apply to you goes under `framework_inputs.<KEY>.excluded` with your reason.

An attestation may also carry `valid_until` (the last day it counts) and `evidence` (pointers to the
documents behind it: a link, a file with its SHA-256, or a record id; never the content). `attested_by` is
a display name rather than an email address, because it is copied into signed artifacts.

## Attestation bundles

Attestations do not have to be typed into the manifest. An **attestation bundle** is a signed JSON document
holding an organisation's attestations and exclusions, served by the endpoint configured in
`OPENCOMPLAI_DASHBOARD_URL`, the endpoint [`push`](../cli/push.md) uploads to. `check`, `gaps`, `recommend`
and `docs generate` merge it into a copy of the manifest's `framework_inputs` once, before anything is
evaluated, so every row sees it. The manifest file on disk is never changed.

Nothing is read or fetched unless you ask for it:

| You ask with | The bundle comes from |
|---|---|
| `--attestations-file PATH` | A file on disk. Offline. |
| `--attestations-remote` | `GET <OPENCOMPLAI_DASHBOARD_URL>/v1/attestations?system_id=<system_id>`, sent with `OPENCOMPLAI_API_KEY` the way `push` sends it. |
| `attestations:` in `opencomplai.yaml` | The same two places, on every run: `source: remote`, or `source: file` with a `path` (a relative path is relative to `opencomplai.yaml`). |

A flag beats `opencomplai.yaml`, and passing both flags exits `2`. With neither a flag nor an `attestations`
section there is no network call.

`opencomplai attestations pull -o bundle.json` writes the fetched bundle to a file (see
[`attestations`](../cli/attestations.md)), so a CI job can keep it and run
`check --attestations-file bundle.json` against the same bytes every time.

### File format

```json
{
  "schema_version": "attestation_bundle/v1",
  "system_id": "loan-decision-model",
  "issued_at": "2026-11-03T09:30:00+00:00",
  "attestations": {
    "ISO_IEC_27001": {
      "ISO_IEC_27001:A.6.3": {
        "statement": "AI security training runs every year for all staff.",
        "attested_by": "Jane Doe",
        "attested_at": "2026-06-01",
        "valid_until": "2027-06-01",
        "evidence": [{ "kind": "link", "ref": "https://wiki.example/training" }],
        "record_id": "rec_1"
      }
    },
    "EU_AI_ACT": {
      "Art. 4": {
        "statement": "AI literacy training is part of onboarding.",
        "attested_by": "Jane Doe",
        "attested_at": "2026-06-01",
        "record_id": "rec_2"
      }
    }
  },
  "excluded": {
    "SOC_2": { "SOC_2:CC1.1": "No office premises." }
  },
  "key_id": "bundle-key-1",
  "signature": "<base64 Ed25519 signature>"
}
```

Every top-level field is required. `system_id` is `null` for an organisation-wide bundle; a bundle for a
different system than the manifest's is refused. Each record has the fields of a manifest attestation plus a
required `record_id`, and `attested_by` must not contain `@`. The bundle is checked against the published
schema ([`attestation_bundle.schema.json`](../concepts/published-schemas.md)) and refused if it is larger
than 2 MiB, before it is parsed.

### Merge rules

- **The manifest wins.** A requirement the manifest already attests or excludes keeps the manifest's entry,
  and a warning names the bundle record or exclusion it shadows.
- **Unknown ids are dropped, with a warning.** So is an id that is not a requirement of that framework, an id
  that does not take an attestation, and a framework key this version does not know.
- **Exclusions are for rows an attestation alone decides.** A row an evaluator or an artifact probe can also
  decide keeps its own status, the EU AI Act takes no exclusions, and NIST AI RMF has no such row; those
  exclusions are dropped with a warning.
- **One record per requirement.** `Art. 4` and `EU_AI_ACT:Art. 4` name the same requirement; if a bundle carries
  both, the first by id is kept and a warning names the other.
- **The EU AI Act** takes only the articles that accept an attestation (Art. 4 today). The bundle's `Art. 4`
  lands under `framework_inputs.EU_AI_ACT.attested`.
- **Frameworks the run does not target are ignored.**

A row attested from a bundle shows `attestation:<name>@<date>#<record_id>` as its `evidence_ref`.

### Expiry

`valid_until` is the last day an attestation counts. From the next day its row reads Unverified, with the
rationale "Attestation expired on <date>", until the attestation is renewed. An attestation without
`valid_until` does not expire, but `gaps` and `check` print a warning when one is older than its row's review
period (365 days for most rows). For a record that came from a bundle, the rationale and the warning both say
to re-attest the record. For a manifest entry, the rationale says to renew it under
`framework_inputs.<FRAMEWORK>.attested` in the manifest, and the warning says to re-attest it or to set
`valid_until` on the attestation.

### Failing a build on unattested rows

`check --gate GDPR --gate-fail-on unverified` (or `gate: {frameworks: [GDPR], fail_on: unverified}` in
`opencomplai.yaml`) fails on Missing and Partial rows, as `partial` does, and also on a row that only an
attestation can decide while it has no current attestation: none recorded, or the one recorded has
expired. The failing ids are in `failed_controls` and the result becomes `CONTROL_FAIL` (exit `1`). Rows that
an evaluator or an artifact can also decide are left to that source, and NIST AI RMF and the EU AI Act are
never failed for being Unverified.

For a job that gates the build, pull the bundle in its own step and give `check` the file with
`--attestations-file`. With `--attestations-remote`, an endpoint that is down leaves the bundle unread, the rows
it attested read Unverified again, and the gate can fail.

### When the bundle cannot be used

- **A file** given with `--attestations-file` (or named in `opencomplai.yaml`) that is missing, too large,
  not valid JSON, not a valid bundle or for another system exits `2`.
- **The endpoint** never blocks a run. If `OPENCOMPLAI_API_KEY` or `OPENCOMPLAI_DASHBOARD_URL` is unset, the key
  contains a space, a newline or a non-ASCII character (it is never printed), the endpoint cannot be reached or answers with an error, or the response is not a valid bundle, the command
  prints a warning and goes on with the manifest alone. The artifact `check` writes then carries
  `"attestation_bundle": {"status": "unavailable", "reason": "<code>"}`, where the code is one of
  `not_configured`, `http_refused`, `invalid_url`, `fetch_failed`, `bundle_too_large`, `invalid_bundle` or
  `system_mismatch`. `gaps`, `recommend` and `docs generate` write no artifact, so for them the warning is
  all there is.
- **Plain `http://`** to any host other than `localhost`, `127.0.0.1` and `::1` is refused (`push` only warns),
  because the API key would travel unencrypted. Other schemes are refused too, and a redirect is never
  followed.

### What the artifact records

With a bundle, the scan artifact gets an `attestation_bundle` block: `sha256`, `signature`, `key_id`,
`issued_at` and `count`, copied from the bundle. The bundle itself is never copied into it. The CLI does not
check the bundle's signature, because it holds no issuer key; the hash and signature are recorded so that the
issuer, or anyone with the issuer's public key, can. `check` records the bundle whether or not the run
evaluates a framework (`--with-gaps` or a gate), so with `attestations: {source: remote}` in
`opencomplai.yaml` every `check` asks the endpoint. A run without a bundle writes the artifact exactly as it
did before.

## What to keep in mind

- **Scope.** The rows cover what each text asks of an organisation or product that builds or runs an AI
  system. They do not replace the full text, an auditor, a supervisor or legal advice.
- **SOC 2.** Rows follow the criteria; attesting them is not a SOC 2 examination, which only a licensed
  CPA firm performs.
- **DORA and EBA.** These packs sit beside the older mapped-only citations: `gaps --map-to DORA|EBA` still
  adds one citation per EU AI Act article to the EU table (see [Mapped regimes](../concepts/mapped-regimes.md)).
  Since DORA applies, the EBA ICT guidelines (GL/2019/04) keep only section 3.8, and the outsourcing
  guidelines (GL/2019/02) are due to be replaced; the rows say so.
- **EIOPA.** The Opinion addresses AI systems that are neither prohibited nor high-risk under the AI Act.
- **CRA.** Every row names when its duty starts: reporting under Art. 14 from 11 September 2026, the rest
  from 11 December 2027.
- **AI Act changes.** Regulation (EU) 2026/1744 moved the special-category basis for bias detection from
  Art. 10(5) to a new Art. 4a and reworded Art. 27(4); links point at the articles as they stand.
