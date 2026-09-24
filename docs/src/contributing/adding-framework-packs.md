# Adding Framework Packs

A framework pack teaches Opencomplai a framework it can assess next to the EU AI Act.
A pack is a data file plus one registry entry and its tests: there are no plugins,
entry points or base classes to implement.

There are two kinds of pack:

- **Native:** a requirements map (JSON) that `build_gap_report` evaluates from evidence
  Opencomplai already gathers: documentation probes, provider attestations, code-scan
  findings and pipeline evaluators. The EU AI Act is native.
- **Derived:** a function that re-projects the EU AI Act gap report into another
  framework's requirements. NIST AI RMF is derived; see
  [NIST AI RMF](../concepts/nist-ai-rmf.md) for how its crosswalk works.

This page walks through a native pack. The design is recorded in
`docs/adr/ADR-framework-packs.md`.

## File locations

| File | Purpose |
|---|---|
| `packages/core/src/opencomplai_core/frameworks.py` | `FrameworkPack` and the `FRAMEWORKS` registry |
| `packages/core/src/opencomplai_core/data/` | Requirements maps and other framework data |
| `packages/core/src/opencomplai_core/gap_probes.py` | Artifact probes (`_PROBE_PATTERNS`) an `artifact` source can name |
| `packages/core/tests/test_framework_packs.py` | Conformance tests every registered pack must pass |
| `packages/core/tests/test_evaluate_targets.py` | Behaviour of `evaluate_targets`, driven by a test-only `FIXTURE` pack |

## Step 1: Write the requirements map

Create `packages/core/src/opencomplai_core/data/<framework>.json`. Every key is a
requirement id prefixed with the framework's registry key (`ACME_AI` in this
example):

```json
{
  "ACME_AI:REQ-1": {
    "title": "Risk register maintained",
    "default_ttl_days": 180,
    "sources": [{ "kind": "artifact", "ref": "risk_register" }]
  },
  "ACME_AI:REQ-2": {
    "title": "Governance policy approved",
    "default_ttl_days": null,
    "sources": [{ "kind": "attestation", "ref": "ACME_AI:REQ-2" }]
  }
}
```

| Field | Rule |
|---|---|
| key | `<KEY>:<id>`, where `<KEY>` is the registry key. The prefix keeps requirement and control ids from colliding with other frameworks'. |
| `title` | Non-empty. Shown in the `gaps` table and used as the control title. |
| `default_ttl_days` | A positive integer, or `null` for evidence that does not go stale. Used as the control's TTL. |
| `sources` | At least one. When several resolve, the worst status wins (Missing, then Partial, then Unverified, then Met). |

Source kinds a native pack may use:

| `kind` | `ref` | Resolved from |
|---|---|---|
| `artifact` | A probe name in `gap_probes._PROBE_PATTERNS`, e.g. `risk_register`, `deployer_instructions` | Documentation and code conventions found under `--repo-root` |
| `attestation` | The requirement's own id | The provider's statement in the manifest's `framework_inputs.<KEY>.attested` |
| `scan` | A `SignalCategory` value | Findings of a supplied code scan (`--scan-report`, `check --scan`) |
| `evaluator` | An evaluator id from `EVALUATOR_REGISTRY` | Results of a supplied eval sample set (`--sample-set`) |

`rule` and `obligation` sources are EU AI Act only. Do not edit
`gap_article_map.json`, the EU AI Act's map. If you need a probe that does not exist,
add it to `_PROBE_PATTERNS` with tests of its own.

Map a requirement only to a source that actually evidences it. When nothing
Opencomplai measures does, use an `attestation` source: the row then reads
**Unverified** until the provider records a statement, and **Met**, labelled
`attested`, once they do. A probe that merely finds a file is not evidence of a
requirement it does not check.

## Step 2: Register the pack

Add one entry to `FRAMEWORKS` in `frameworks.py`:

```python
FRAMEWORKS: dict[str, FrameworkPack] = {
    # ... EU_AI_ACT and NIST_AI_RMF ...
    "ACME_AI": FrameworkPack(
        "ACME_AI",
        "ACME AI Standard 1.0",
        requirements=_DATA_DIR / "acme_ai.json",
    ),
}
```

- The registry key, the pack `id` and the requirement id prefix are the same string.
- `label` is the name `gaps`, `report` and the framework reports show.
- Leave `disclaimer_ref` at its default, the framework-neutral `DISCLAIMER_V2`.
  `DISCLAIMER_V1` names the EU AI Act and belongs to it alone.
- A derived pack sets `derive` instead of `requirements`, never both, and lists every
  data file the function reads in `data_files`, so `data_version` changes when they
  do. Its rows must carry the prefix too.

Targets are registry keys, so the new key works in `compliance_targets`, `--target`,
`framework_inputs` and `gate.frameworks` at once. Do not add it to the
`ComplianceTarget` enum: the legacy single `compliance_target` stays limited to
`EU_AI_ACT` and `NIST_AI_RMF`, which keeps the Annex IV dossier schema stable.

## Step 3: Test it

`test_framework_packs.py` runs every registered pack through its conformance checks
without any change on your side: exactly one of `requirements` and `derive`, prefixed
ids, non-empty titles, valid TTLs, known source kinds and refs, attestation refs equal
to their own id, and a stable 12-character `data_version`.

Add behaviour tests for what the pack should conclude, in the style of
`test_evaluate_targets.py`: build a `SystemManifest` that targets the framework, call
`evaluate_targets` with a `repo_root` holding (or lacking) the evidence, and assert
the status of each row, the effect of an exclusion and of an attestation.

Run the core and CLI suites:

=== "macOS / Linux"
    ```bash
    uv run pytest packages/core packages/cli -q
    ```

=== "Windows (PowerShell)"
    ```powershell
    uv run pytest packages/core packages/cli -q
    ```

The EU AI Act golden snapshots in `packages/cli/tests/golden/` must still match byte
for byte. A new pack never changes EU AI Act output; if a snapshot fails, the pack has
leaked into the EU path. Do not regenerate the snapshots to make the test pass.

`scripts/smoke_wheel_install.sh` builds and installs the wheels in a clean venv; run it
to confirm the new data file ships.

## What the pack gets without further code

Once registered, a native pack is carried everywhere a framework is:

- `gaps` prints its table, and `gaps --output json` includes it in `frameworks`;
- `check --with-gaps` embeds it in `framework_reports`, and `check --gate` can gate on it;
- `report` renders a section for it;
- `recommend` writes `generic_requirement.md` for its Missing and Partial rows;
- the control catalog takes its titles and TTLs, and `gaps` / `check --with-gaps` sync
  its requirements to the control register (`controls status --framework <KEY>`);
- `framework_inputs.<KEY>` accepts exclusions, and attestations for requirements with
  an `attestation` source.

## Step 4: Document it

Add a row to the status table on [Frameworks](../frameworks/index.md), saying plainly
whether the framework is evaluated natively, derived, or only mapped, and what it does
not cover. Add a CHANGELOG entry under `[Unreleased]`.
