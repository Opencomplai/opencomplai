# Project configuration (`opencomplai.yaml`)

An optional, per-repo YAML file for setting `scan` defaults and choosing which
frameworks gate `check`, so a team doesn't have to repeat the same CLI flags on every
invocation or in every CI job.

!!! info "Behavior only — never a compliance declaration"
    `opencomplai.yaml` governs tool *behavior* (scan defaults, evaluator threshold
    overrides, allowlists) — it is **never** a source of compliance *declarations*.
    `system-manifest.json` (`SystemManifest`) remains the sole authority for what a
    system is declared to do. Setting `scan.fail_on: critical` in `opencomplai.yaml`
    changes when a scan gates CI; it says nothing about whether the system is actually
    compliant. Likewise `gate` decides which frameworks' gaps fail CI; exclusions and
    attestations belong in the manifest's `framework_inputs`.

## File location

`opencomplai.yaml` is auto-discovered from `--repo-root` — place it at the root of the
repository you pass to `opencomplai scan --repo-root` (or `check` / `gaps
--repo-root`). `controls status` reads it from the current directory. If absent, every
field falls back to its built-in default; there is no error for a missing file. A
malformed file (not valid YAML, a section that is not a mapping, or `gate.frameworks`
that is not a list) exits `2`.

## Supported keys

Currently four keys are supported. **This list will grow** — treat any key not listed
here as unsupported in the current release.

```yaml
scan:
  fail_on: critical           # none | new-major | major | critical
  framework_detectors: true   # opt in to AST-level framework-object detection
gate:
  frameworks: [NIST_AI_RMF]   # target frameworks other than EU_AI_ACT that gate check
  fail_on: missing            # missing (default) | partial
```

| Key | Type | Overrides |
|---|---|---|
| `scan.fail_on` | string | The default for `opencomplai scan --fail-on` |
| `scan.framework_detectors` | boolean | The default for `opencomplai scan --framework-detectors` |
| `gate.frameworks` | list of strings | The default for `opencomplai check --gate`, and the frameworks `controls status` counts besides `EU_AI_ACT`. See [Gating other frameworks](../cli/check.md#gating-other-frameworks) |
| `gate.fail_on` | string | The default for `opencomplai check --gate-fail-on` |

## Precedence

**Explicit CLI flag > `opencomplai.yaml` > built-in default.** An explicit CLI flag
always wins — the config file only fills in a value when the CLI flag was left at its
built-in default (i.e. you didn't pass it at all).

### Worked example

Given this `opencomplai.yaml`:

```yaml
scan:
  fail_on: critical
```

Running `scan` with no `--fail-on` flag uses the config value:

=== "macOS / Linux"
    ```bash
    opencomplai scan --manifest system-manifest.json --repo-root .
    # equivalent to --fail-on critical
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scan --manifest system-manifest.json --repo-root .
    # equivalent to --fail-on critical
    ```

A `major`-severity fixture **passes** here (`critical` only gates on critical-severity
gaps). But an explicit `--fail-on major` on the same fixture and same config file
**fails** — the CLI flag overrides the config file:

=== "macOS / Linux"
    ```bash
    opencomplai scan --manifest system-manifest.json --repo-root . --fail-on major
    # explicit flag wins over opencomplai.yaml's fail_on: critical
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scan --manifest system-manifest.json --repo-root . --fail-on major
    # explicit flag wins over opencomplai.yaml's fail_on: critical
    ```

When a project config is loaded, `scan` prints a one-line confirmation:

```text
Loaded project config: opencomplai.yaml
```

## Gating other frameworks (`gate`)

The EU AI Act always gates `opencomplai check`. `gate` opts other target frameworks in:

```yaml
gate:
  frameworks: [NIST_AI_RMF]
  fail_on: partial
```

- `frameworks`: target frameworks other than `EU_AI_ACT` whose failing rows fail
  `check` (exit `1`). Each must be among the run's targets: the manifest's
  `compliance_targets`, or `check --target`.
- `fail_on`: `missing` (the default) fails on Missing rows; `partial` on Missing and
  Partial rows. Excluded, Unverified and Met rows never fail.
- `check --gate` (repeatable) replaces `frameworks`, and `--gate-fail-on` replaces
  `fail_on`.
- `controls status` counts the gated frameworks' controls as well as the EU AI Act's,
  and `gaps` notes under a gated framework's table that it is gated.
- `EU_AI_ACT` in the list, an unknown framework, a framework that is not a target or a
  `fail_on` other than `missing` or `partial` exits `2` before anything is written.

The frameworks themselves, and any exclusions or attestations, are declared in the
manifest, not here. See [Frameworks](../frameworks/index.md) and
[Gating other frameworks](../cli/check.md#gating-other-frameworks).

## Relationship to other config

`opencomplai.yaml` is **additive to** — not a replacement for — `.ocignore` (scan
inclusion/exclusion patterns and inventory limits, see the
[scanner guide](../getting-started/scanner.md#ocignore)) and explicit CLI flags.
Each governs a different concern:

| File / flag | Governs |
|---|---|
| `system-manifest.json` | Compliance *declaration* — `intended_purpose`, risk presumption, Annex IV fields, target frameworks (`compliance_targets`) and their exclusions and attestations (`framework_inputs`). Sole source of truth. |
| `.ocignore` | What the scanner walks/reads — exclusion patterns, inventory limits. |
| `opencomplai.yaml` | Tool *behavior* defaults — `scan --fail-on`, `scan --framework-detectors`, `check --gate`, `check --gate-fail-on`. |
| CLI flags | Always override both `.ocignore` defaults' equivalent settings (where applicable) and `opencomplai.yaml`. |

See [scan CLI reference](../cli/scan.md) for the full flag table these keys map onto.
