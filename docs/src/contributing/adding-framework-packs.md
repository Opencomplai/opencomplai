# Adding Framework Packs

A framework pack teaches Opencomplai a framework it can assess next to the EU AI Act.
A pack is one directory of JSON files and its tests: there are no plugins, entry points,
base classes or registry tables to edit. Packs are discovered from the directories.

This page walks through a native pack: a requirements map that `build_gap_report`
evaluates from evidence Opencomplai already gathers. The EU AI Act is native. NIST AI RMF
is derived: it re-projects the EU AI Act gap report; see
[NIST AI RMF](../concepts/nist-ai-rmf.md). The design is recorded in
`docs/adr/ADR-framework-packs.md`.

## Pack layout

One directory per pack, `packages/core/src/opencomplai_core/packs/<KEY>/`, where `<KEY>`
is the registry key (`ACME_AI` in the examples below).

| File | Required | Purpose |
|---|---|---|
| `pack.json` | yes | The pack's identity: key, name, kind, caveat, disclaimer reference and the data files it reads |
| `requirements.json` | yes | The requirements map: one entry per requirement |
| `applicability.json` | no | Yes/no scope questions and the outcomes their answers give (see [scope](../cli/scope.md)) |
| `probes.json` | no | Documentation probes of the pack's own, which an `artifact` source can name |
| `timeline.json` | no | Application dates for requirements |
| `templates/` | no | Remediation templates that `recommend` writes for Missing and Partial rows |
| `scaffolds/` | no | Fill-in documents that [scaffold](../cli/scaffold.md) writes |

Shared code stays where it is: `gap_probes.py` holds the shared artifact probes
(`_PROBE_PATTERNS`), and `packages/core/tests/test_framework_packs.py` runs conformance
checks over every pack it finds.

## Step 1: Write the requirements map

Create `requirements.json`. Every key is a requirement id prefixed with the pack's key:

```json
{
  "ACME_AI:REQ-1": {
    "title": "Risk register maintained",
    "default_ttl_days": 180,
    "evidence_class": "hybrid",
    "sources": [{ "kind": "artifact", "ref": "risk_register" }]
  },
  "ACME_AI:REQ-2": {
    "title": "Governance policy approved",
    "default_ttl_days": null,
    "evidence_class": "organisational",
    "sources": [{ "kind": "attestation", "ref": "ACME_AI:REQ-2" }],
    "note": "Evidence that a person has confirmed the governance policy is approved."
  }
}
```

| Field | Rule |
|---|---|
| key | `<KEY>:<id>`. The prefix keeps requirement and control ids from colliding with other frameworks'. Clause ids are hyphenated (`early-warning`), never underscored. |
| `title` | Non-empty. Shown in the `gaps` table and used as the control title. |
| `default_ttl_days` | A positive integer, or `null` for evidence that does not go stale. Used as the control's TTL. |
| `evidence_class` | `machine`, `hybrid` or `organisational`: how much of the row the tool can check without a person. |
| `sources` | At least one. When several resolve, the worst status wins (Missing, then Partial, then Unverified, then Met). A source can carry a `role` (see below). |
| `scope_out` | Optional. A list of groups of answer keys from `framework_inputs.<KEY>.scope`. When every answer in any one group is `false`, the row leaves the report and is listed under `excluded` with a generated reason. An explicit exclusion keeps its own reason, and a row with a recorded attestation stays. |

Source kinds a pack may use:

| `kind` | `ref` | Resolved from |
|---|---|---|
| `attestation` | The requirement's own id | The provider's statement in the manifest's `framework_inputs.<KEY>.attested` |
| `artifact` | A probe name, from `_PROBE_PATTERNS` or the pack's own `probes.json` | Documentation and code conventions found under `--repo-root` |
| `evaluator` | An evaluator id from `EVALUATOR_REGISTRY` | Results of a supplied eval sample set (`--sample-set`) |
| `scan` | A `SignalCategory` value | Findings of a supplied code scan (`--scan-report`, `check --scan`) |
| `manifest` | A manifest field name the validator knows | What the system manifest declares |
| `record` | A record name the validator knows | A record the tool itself keeps |

`rule` and `obligation` sources are EU AI Act only. Do not edit the EU AI Act pack from a
new pack. If you need a probe that does not exist, add it to the pack's `probes.json` (or,
for a shared one, to `_PROBE_PATTERNS`) with tests of its own. A probe can require content
markers; one that reads code sets `select`, so only the matched files that satisfy the
markers count.

Map a requirement only to a source that actually evidences it. When nothing Opencomplai
measures does, use an `attestation` source: the row then reads **Unverified** until the
provider records a statement, and **Met**, labelled `attested`, once they do. A probe that
merely finds a file is not evidence of a requirement it does not check.

### Roles

A source has no role when it decides the row. Two roles change how a probe source
combines with an attestation:

| `role` | Effect |
|---|---|
| `supporting` | A probe never reads Met, so a plain `artifact` source next to an `attestation` would turn an attested row Partial or Missing. Marked `supporting`, the probe only adds to the rationale: the row stays Met when the others are Met, and stays Unverified when the others are Unverified and the probe found evidence (the rationale says it was found and is not attested). Nothing changes when the probe finds nothing, or when the others resolve to Missing or Partial. |
| `corroborating` | A probe that checks an attestation. When the attestation is valid and a probe finds evidence, the row stays Met and is marked corroborated. When no probe finds evidence, the row drops to Partial and the rationale says it was attested with no supporting evidence found. Without a valid attestation, the probe decides the row. |

`test_framework_packs.py` checks that a role appears only next to at least one source
without one. Keep the attestation source first.

## Step 2: Describe the pack

Create `pack.json`:

```json
{
  "id": "ACME_AI",
  "order": 20,
  "kind": "native",
  "name": "ACME AI Standard 1.0",
  "short_name": "ACME AI",
  "caveat": "a draft estimate, not an assurance",
  "disclaimer_ref": "DISCLAIMER_V2",
  "requirements": "requirements.json",
  "data_files": ["applicability.json", "probes.json"]
}
```

- The directory name, the pack `id` and the requirement id prefix are the same string.
- `name` is what `gaps`, `report` and the framework reports show.
- Leave `disclaimer_ref` at the framework-neutral `DISCLAIMER_V2`. `DISCLAIMER_V1` names
  the EU AI Act and belongs to it alone.
- List every data file the pack reads in `data_files`, so `data_version` changes when
  they do.
- A derived pack sets `kind` to `derived` and names the function that re-projects the EU AI
  Act report; its rows carry the prefix too.

Targets are registry keys, so the new key works in `compliance_targets`, `--target`,
`framework_inputs` and `gate.frameworks` at once. Do not add it to the `ComplianceTarget`
enum: the legacy single `compliance_target` stays limited to `EU_AI_ACT` and
`NIST_AI_RMF`, which keeps the Annex IV dossier schema stable.

### Optional files

- `applicability.json`: `questions` (a `key`, the `text` asked and what a `false` answer
  means), a `default` outcome, and `outcomes` that say which answers give `applies` or
  `not_applicable`, each with a reason. Users answer it with `opencomplai scope <KEY>`.
- `scaffolds/scaffolds.json`: per document an id, a `title`, a `target` path and the file
  to copy. `opencomplai scaffold <KEY>` writes them, with `_fill in_` placeholders.
- `templates/`: markdown templates and a `template_map.json` that ties each requirement
  to one.
- `timeline.json`: entries with an id, a title, an `applies_from` date and the
  requirements it covers.

For ISO, AICPA and ETSI material, write requirement ids and your own "Evidence that ..."
wording only. Do not copy or closely paraphrase the standard's text.

## Step 3: Validate it

From the repository root:

=== "macOS / Linux"
    ```bash
    uv run python tools/packs/validate_pack.py ACME_AI --strict
    uv run python tools/packs/parity_check.py ACME_AI
    ```

=== "Windows (PowerShell)"
    ```powershell
    uv run python tools/packs/validate_pack.py ACME_AI --strict
    uv run python tools/packs/parity_check.py ACME_AI
    ```

`validate_pack.py` checks the data shape. `parity_check.py` compares the pack with the
rest of the product and writes the pack's status word; never type that word into a file.

`test_framework_packs.py` runs every discovered pack through its conformance checks
without any change on your side: prefixed ids, non-empty titles, valid TTLs, known source
kinds and refs, attestation refs equal to their own id, `scope_out` groups that use only
declared answers, and a stable 12-character `data_version`.

Add behaviour tests for what the pack should conclude, in the style of
`test_evaluate_targets.py`: build a `SystemManifest` that targets the framework, call
`evaluate_targets` with a `repo_root` holding (or lacking) the evidence, and assert the
status of each row, the effect of an exclusion and of an attestation.

Run the core and CLI suites:

=== "macOS / Linux"
    ```bash
    uv run pytest packages/core packages/cli -q
    ```

=== "Windows (PowerShell)"
    ```powershell
    uv run pytest packages/core packages/cli -q
    ```

The EU AI Act golden snapshots in `packages/cli/tests/golden/` must still match byte for
byte. A new pack never changes EU AI Act output; if a snapshot fails, the pack has leaked
into the EU path. Do not regenerate the snapshots to make the test pass.

`scripts/smoke_wheel_install.sh` builds and installs the wheels in a clean venv; run it
to confirm the new data files ship.

## What the pack gets without further code

Once its directory exists, a native pack is carried everywhere a framework is:

- `gaps` prints its table, and `gaps --output json` includes it in `frameworks`;
- `check --with-gaps` embeds it in `framework_reports`, and `check --gate` can gate on it;
- `report` renders a section for it;
- `recommend` writes remediation files for its Missing and Partial rows, from its
  templates when it has them;
- the control catalog takes its titles and TTLs, and `gaps` / `check --with-gaps` sync its
  requirements to the control register (`controls status --framework <KEY>`);
- `framework_inputs.<KEY>` accepts scope answers, exclusions, and attestations for
  requirements with an `attestation` source.

## Step 4: Document it

Add a page for the pack under `docs/src/frameworks/` and a row to the status table on
[Frameworks](../frameworks/index.md), saying plainly whether the framework is evaluated
natively, derived, or only mapped, and what it does not cover. Add a CHANGELOG entry
under `[Unreleased]`. Say "draft estimate" for any percentage, and never describe a result
as compliant, certified or audited.
