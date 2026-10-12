# check

Run a full compliance check against EU AI Act rules. Other target frameworks can be
assessed alongside (`--with-gaps`) and, if you opt in, gate the check too (see
[Gating other frameworks](#gating-other-frameworks) and [Frameworks](../frameworks/index.md)).

If the manifest has no `checker_session`, `check` prints a **non-blocking** warning recommending `opencomplai checker` or `opencomplai init --interactive`. When a session is present, human output includes a one-line applicability summary.

A `checker_session.verdict` of `prohibited_practice` fails the check with
`POLICY_BLOCK` (exit `3`, `EU_AIA_ART5_UNACCEPTABLE`); `high_risk_ai_system`
fails it with at least `CONTROL_FAIL` (exit `1`, `EU_AIA_ART6_HIGH_RISK`). The
verdict only ever raises the result: it never replaces `TRAP_DETECTED` or
`VALIDATION_FAIL`. Manifests written by 0.7.0 `opencomplai checker
--write-manifest` hold the verdict in `intended_purpose` instead; `check`
still applies it and warns you to replace `intended_purpose` with what the
system does.

A signed acceptance record committed under `.opencomplai/acceptances/` (written
by [`accept`](accept.md)) stops `EU_AIA_ART6_HIGH_RISK` counting as a failure.
Art. 5 and traps are unaffected, and a record that is stale (the manifest
changed after it was signed), unsigned or tampered is reported on stderr and
does not clear anything.

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai check [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check [OPTIONS]
    ```

## Options

| Option | Default | Description |
|---|---|---|
| `--manifest` / `-m` | `system-manifest.json` | Path to the system manifest JSON file. Repeat it for several systems, or pass a glob; see [Several manifests](#several-manifests). |
| `--commit-ref` | `HEAD` | Git commit reference for the assessment. `HEAD` or a value under 7 characters is replaced by the CI commit variable (`GITHUB_SHA`, `CI_COMMIT_SHA`), else `git rev-parse HEAD` in `--repo-root`, else `unresolved`. The resolved value is used everywhere, including the artifact and `gap_report`. |
| `--scan-mode` | `local` | `ci`, `local`, or `airgap`. Recorded in the artifact and used as the assessment's `deployment_context`. `ci` makes a degraded-complete scan exit `1`; `local` and `airgap` exit `0`. `airgap` does not block network access. |
| `--sample-set` | *(none)* | Path to an `EvalSampleSet` JSON to run the safety / bias / data-leakage evaluators. Its `system_id` must match the manifest. With several manifests the CLI rewrites `system_id` in a per-system copy; see [Several manifests](#several-manifests). |
| `--sign` / `--no-sign` | `--no-sign` | Sign the status artifact with the key in `~/.opencomplai/signing.key` or, when set, `SIGNING_KEY_PRIVATE` (base64 PEM). Exits `2` before doing anything if there is no key. |
| `--sign-if-available` | off | Sign when a key is available; otherwise print a warning and write an unsigned artifact. `--sign` wins when both are given. |
| `--scan` | off | Run the opt-in code corroboration scan under `--repo-root` and add its summary to the artifact. See [scan](scan.md). |
| `--fail-on` | `none` | With `--scan`: fail the check on scan discrepancy severity. One of `none`, `new-major`, `major`, `critical`; the levels are the ones in [scan](scan.md). A detector or scan error fails the check at any level. |
| `--baseline` | *(none)* | With `--scan`: JSON file with `accepted_categories`, the categories `--fail-on new-major` treats as already accepted (see [scan](scan.md)). A file that cannot be read exits `2`. |
| `--emit-evidence` / `--no-emit-evidence` | `--emit-evidence` | With `--scan`: append the `code_corroboration` event to the evidence ledger, or not. |
| `--strict` | off | Exit `2` on unknown top-level keys in the manifest instead of warning and ignoring them. |
| `--with-gaps` | off | Attach a per-article `gap_report` to the artifact (additive, informational only). Artifact-backed articles are probed under `--repo-root`, as in [`gaps`](gaps.md). |
| `--repo-root` | `.` | Repo root for the `--scan` code scan and the `--with-gaps` artifact path probes (Arts. 9/13/14/16/24/43). |
| `--change-context` | *(none)* | Declared reason for this deployment's change, such as `model_retrain`, `purpose_change` or `capability_extension`. A recognised value trips the Article 25 substantial-modification trap (exit `4`) and freezes deployment pending review. See [Exit codes](exit-codes.md). |
| `--target` | manifest | Framework `--with-gaps` and `--gate` assess; repeat for several. Replaces the manifest's `compliance_targets`, else its `compliance_target`. `NIST_AI_RMF` attaches `nist_rmf_report`. Any set other than exactly `EU_AI_ACT` or exactly `NIST_AI_RMF` also attaches `framework_reports`, one report per target. |
| `--gate` | `opencomplai.yaml` | Target framework other than the EU AI Act whose failing rows fail the check; repeat for several. Replaces `gate.frameworks` from `opencomplai.yaml`. See [Gating other frameworks](#gating-other-frameworks). |
| `--gate-fail-on` | `missing` | `missing` or `partial`: which rows of a gated framework fail. Replaces `gate.fail_on` from `opencomplai.yaml`. |
| `--require-exemption-record` | off | Opt-in. When the manifest's checker session relies on the Art. 6(3) derogation (it lists `provider_art_6_4_registration`) and the repository holds no valid signed `art_6_3_exemption` record, `check` fails with `EU_AIA_ART6_3_EXEMPTION_RECORD` (exit `1`). A record that is absent, unsigned, tampered, untrusted or stale (the manifest or its grounds changed after signing) counts as missing. Without the flag the exit code is unchanged and the `--with-gaps` Art. 49 row only reports the record. Write the record with [`accept --exemption`](accept.md). The record is the provider's own declaration of the grounds; the check does not assess whether the exemption is valid. Wording is product design, flagged `needs_founder_review`. |
| `--oversight-log` | state directory | Oversight log to summarise into the artifact. Default: the oversight log in the OpenComplAI state directory. |
| `--agent-log` | `agent-log.jsonl` | Agent decision log to summarise into the artifact. |
| `--incident-register` | `incident-register.json` | Incident register to summarise into the artifact. |
| `--output-dir` | `.` | Directory where `compliance-artifact.json` and the scan and eval sidecars are written. With several manifests it holds one directory per system; see [Several manifests](#several-manifests). |
| `--report-junit` | *(none)* | Also write a JUnit XML report of the verdict to this path. With several `--manifest` values each system gets its own file; see [Several manifests](#several-manifests). |
| `--sarif-output` | *(none)* | Also write the check verdict as SARIF 2.1.0 to this path. It is the verdict, not scan evidence. With several `--manifest` values each system gets its own file; see [Several manifests](#several-manifests). |
| `--summary-md` | *(none)* | Also write the Markdown job summary to this path. With several `--manifest` values each system gets its own file; see [Several manifests](#several-manifests). |
| `--output` / `-o` | `human` | Output format: `human` or `json`. |

The three log options feed the `summaries` block of the artifact. The summaries are built
before signing, so a signed artifact covers them. A missing file is not an error, and a
summary that cannot be built is left out with a warning.

With `--scan`, a classification proposal that you confirmed (written by
[`scan --propose`](scan.md#suggesting-a-classification-propose), confirmed by
[`accept --proposal`](accept.md#confirming-a-classification-proposal)) and that names an
Annex III area your declared purpose does not cover adds a `confirmed_proposal:<area>`
row to the scan summary, for example `confirmed_proposal:employment`. The row counts as
`major` under `--fail-on`, so `--fail-on major` and `--fail-on new-major` fail the check
and `--fail-on critical` and `none` do not. A missing, unconfirmed, edited or stale
proposal changes nothing, and the declared purpose stays the source of the
classification.

## Several manifests

Pass `-m` more than once (or a glob such as `-m "systems/*.json"`; the CLI expands
globs itself, so quoting works the same in PowerShell) to check several systems in
one command. Each manifest is run through the normal single-system `check`, in order,
and a failing system never stops the rest.

```bash
opencomplai check -m a.json -m b.json --output-dir out
```

```text
out/
  alpha/compliance-artifact.json     # one directory per system_id
  alpha/sample-set.json              # only with --sample-set
  beta/compliance-artifact.json
  portfolio-summary.json
```

One shared `--sample-set` serves every system. For each system the CLI writes
`<output-dir>/<system_id>/sample-set.json`, the same set with `system_id` set to that
system's id, and that copy is what the child run reads. The file you passed is never
modified. An unreadable or invalid set is reported per system exactly as in a single run.

One manifest describes exactly one system. A manifest with a top-level `systems` key,
or one that is a JSON array, is rejected with exit `2` and nothing is written. Two
manifests with the same `system_id` also exit `2` before anything runs. Directory names
are the `system_id` with every character outside `A-Za-z0-9._-` replaced by `_`.

With `--report-junit`, `--sarif-output` or `--summary-md`, each system gets its own file
named `<stem>.<system_id><ext>` beside the path you gave. The `system_id` goes through the
same character rule as the directory names. A single-manifest run writes the exact path given.

```text
opencomplai check -m a.json -m b.json --report-junit r.xml
# writes r.alpha.xml and r.beta.xml
```

`portfolio-summary.json` is **unsigned and informational**. It has no timestamp:

```json
{
  "kind": "portfolio_summary",
  "schema_version": "1",
  "signed": false,
  "worst_exit_code": 1,
  "systems": [
    {
      "system_id": "alpha",
      "manifest": "a.json",
      "exit_code": 1,
      "result": "control_fail",
      "failed_controls": ["..."],
      "artifact": "alpha/compliance-artifact.json",
      "artifact_sha256": "..."
    }
  ]
}
```

`artifact` and `artifact_sha256` are `null` when a system wrote no artifact (for example
a missing or invalid manifest). The process exits with the **worst severity**, the
numeric maximum of the per-system codes: 4 trap > 3 policy block > 2 validation >
1 control fail > 0 pass. The summary file is the machine interface; with `--output json`
stdout is not a single document because each system also prints. `opencomplai push`
still takes one artifact at a time.

## Environment variables

| Variable | Description |
|---|---|
| `OPENCOMPLAI_API_URL` | When set, `check` orchestrates all services via the gateway API at this URL (service-backed mode). When unset, runs locally. Example: `http://localhost:8080` |
| `OPENCOMPLAI_CHECK_ARGS` | Read by `opencomplai-gha-connector` and `opencomplai-gitlab-connector`, not by `check` itself. Extra `check` flags, shell-style, followed by the connector's own flags and then the command-line flags; malformed text exits `2`. The [GitHub Action](../guides/github-action.md) does not read it; it has an `args` input. |

## Examples

=== "macOS / Linux"
    ```bash
    # Local check with human-readable output (default)
    opencomplai check

    # Run pipeline evaluators against your own model outputs
    opencomplai check --sample-set eval-set.json

    # Assess the EU AI Act and NIST AI RMF side by side, and let NIST AI RMF gate too
    opencomplai check --with-gaps --target EU_AI_ACT --target NIST_AI_RMF --gate NIST_AI_RMF

    # CI-mode with JSON output piped to jq
    opencomplai check --scan-mode ci --output json | jq .result

    # Service-backed mode (Docker Compose stack running)
    OPENCOMPLAI_API_URL=http://localhost:8080 opencomplai check

    # Air-gap mode
    opencomplai check --scan-mode airgap
    ```

=== "Windows (PowerShell)"
    ```powershell
    # Local check with human-readable output (default)
    opencomplai check

    # Run pipeline evaluators against your own model outputs
    opencomplai check --sample-set eval-set.json

    # Assess the EU AI Act and NIST AI RMF side by side, and let NIST AI RMF gate too
    opencomplai check --with-gaps --target EU_AI_ACT --target NIST_AI_RMF --gate NIST_AI_RMF

    # CI-mode with JSON output (pipe to ConvertFrom-Json for parsing)
    opencomplai check --scan-mode ci --output json | ConvertFrom-Json | Select-Object -ExpandProperty result

    # Service-backed mode (Docker Compose stack running)
    $env:OPENCOMPLAI_API_URL = "http://localhost:8080"; opencomplai check

    # Air-gap mode
    opencomplai check --scan-mode airgap
    ```

## Output

After every run, `compliance-artifact.json` is written to the current directory.
This is the canonical `ScanStatusArtifact` for CI consumption.

**Human output example** (a passing, minimal-risk system):

```text
Evals: no eval sample set supplied (skipped)

Opencomplai Compliance Check
  system_id:    my-model
  commit_ref:   HEAD
  result:       PASS
  duration_ms:  0
  signed:       no (OSS unsigned)

  Artifact written to compliance-artifact.json
```

When a control fails, a `failed_controls:` line is added, e.g. for a high-risk
use case:

```text
Opencomplai Compliance Check
  system_id:    hiring
  commit_ref:   HEAD
  result:       CONTROL_FAIL
  duration_ms:  0
  signed:       no (OSS unsigned)
  failed_controls: EU_AIA_ART6_HIGH_RISK

  Artifact written to compliance-artifact.json
```

With `--sample-set`, the `Evals: ...skipped` line is replaced by an
`eval_outcome:` line (`pass`, `warn`, or `fail`).

**JSON output (`ScanStatusArtifact` schema):**

```json
{
  "install_id": "a1b2c3d4-...",
  "system_id": "my-model",
  "commit_ref": "HEAD",
  "result": "pass",
  "failed_controls": [],
  "evidence_hashes": [],
  "rationale_hash": "sha256:...",
  "duration_ms": 0,
  "pending_verifications_count": 0,
  "signature": null,
  "eval_summary": null
}
```

`eval_summary` is populated only when `--sample-set` is supplied; `signature` is
populated only when `--sign` (or `--sign-if-available` with a key) is supplied.
`check` stamps `timestamp` (UTC, `Z` suffix) and `policy_bundle_version`
(`cli-<version>`) when they are unset, then signs last, over the artifact
exactly as written — including the stamped fields, the `--scan --fail-on`
result, the checker verdict and the `--with-gaps` blocks — so
`compliance-artifact.json` verifies against `signing.pub` as-is and
`opencomplai push` keeps the signature. Without a key, `--sign` exits `2`
and writes nothing; use `--sign-if-available` to get an unsigned artifact
and a warning instead.

With `--with-gaps`, the artifact also carries `gap_report` (the EU AI Act, per
article) and, when `NIST_AI_RMF` is a target, `nist_rmf_report`, both exactly as in
earlier releases. When the targets are anything other than exactly `EU_AI_ACT` or
exactly `NIST_AI_RMF`, it adds `framework_reports`: one framework report per target,
in target order, the same shape as the `frameworks` block of
[`gaps --output json`](gaps.md#several-frameworks), with `gated: true` on each gated
framework. Otherwise the key is left out, so the artifact's bytes and signature are
the same as before.

`check` also writes `scan-report.json` / `eval-report.json` sidecars next to
`compliance-artifact.json` whenever a scan (`--scan`) or eval (`--sample-set`)
actually ran — these are what `opencomplai docs generate` picks up
automatically to populate the Annex IV dossier's wired-evidence fields. See
[Annex IV coverage ledger](../concepts/annex-iv-coverage.md).

### Reports for CI

Three options write a report of the verdict next to the artifact, after it has been written:
`--report-junit` (JUnit XML, for a test-results view), `--sarif-output` (SARIF 2.1.0, for code
scanning; it carries the verdict, not scan evidence, so `scan --sarif-output` is the one for
scan findings) and `--summary-md` (Markdown, for a pull request comment or job summary). Each
is optional and independent. With several `--manifest` values, see
[Several manifests](#several-manifests).

=== "macOS / Linux"
    ```bash
    opencomplai check --output-dir out --report-junit out/check.xml --sarif-output out/check.sarif --summary-md out/summary.md
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check --output-dir out --report-junit out/check.xml --sarif-output out/check.sarif --summary-md out/summary.md
    ```

## Gating other frameworks

Only the EU AI Act gates `check` by default. To make another target framework
fail CI as well, list it under `gate` in `opencomplai.yaml` (read from
`--repo-root`) or pass `--gate`:

```yaml
gate:
  frameworks: [NIST_AI_RMF]
  fail_on: missing   # or partial
```

`check` then assesses the targets even without `--with-gaps`. A row of a gated
framework fails when it is **Missing**, or **Missing** or **Partial** with
`fail_on: partial`. Rows excluded in the manifest's `framework_inputs` never
fail, and neither do **Unverified** or **Met** rows. Failing ids, prefixed
`<FW>:` (e.g. `NIST_AI_RMF:GOVERN 1.1`), follow the EU AI Act ids in
`failed_controls`. The only result a gate changes is `PASS`, which becomes
`CONTROL_FAIL` (exit `1`); a gate never halts the system. With `--with-gaps`,
each gated framework's entry in `framework_reports` has `gated: true`.

A bad gate exits `2` before anything is written: the EU AI Act listed (its
controls already gate), an unknown framework, a framework that is not among
the targets, or a `fail_on` other than `missing` or `partial`.

## High-risk acceptance

An [acceptance record](accept.md) acknowledges the Art. 6 high-risk classification. It does
not state that the system is compliant and it removes no other obligation, so Missing EU
AI Act rows still fail the check. Without a record, `check` behaves as before. The matrix is also in [Exit codes](exit-codes.md#high-risk-acceptance).

| Case | Exit | `failed_controls` |
|---|---:|---|
| Not accepted (no record) | `1` | `EU_AIA_ART6_HIGH_RISK`, unchanged |
| Accepted, no Missing EU rows | `0` | `EU_AIA_ART6_HIGH_RISK` is gone |
| Accepted, Missing EU rows | `1` | the Missing article ids, such as `Art. 9`; the Art. 6 row is not counted |
| Stale or invalid record (edited manifest, unsigned, tampered, untrusted) | `1` | `EU_AIA_ART6_HIGH_RISK`, with a warning on stderr |

A prohibited (Article 5) result is always `3`, whatever the record. A valid trap approval
for the same `--change-context`, together with a valid acceptance, replaces exit `4` with
the accepted-path result above and does not halt the system; without both, exit `4` and the
halt are unchanged. An approval alone is not honoured.

## Halt on trap / unresolved HIGH-risk gap

A `TRAP_DETECTED` result, or a HIGH-risk system with an unresolved
corroboration gap (HIGH risk class plus a failed `--scan --fail-on ...`
gate), persists the system as `HALTED_PENDING_REVIEW`. While halted,
`opencomplai docs generate` for that `system_id` refuses outright (exit `4`,
no dossier written, no `--force`). Resume with `opencomplai approve` /
`opencomplai resume` — see
[Halt / resume gate](exit-codes.md#halt-resume-gate-opencomplai-check-opencomplai-docs-generate).

## Exit codes

See [Exit codes](exit-codes.md) for the full table.
