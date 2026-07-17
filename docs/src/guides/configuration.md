# Project configuration (`opencomplai.yaml`)

An optional, per-repo YAML file for setting `scan` defaults, so a team doesn't have to
repeat the same CLI flags on every invocation or in every CI job.

!!! info "Behavior only — never a compliance declaration"
    `opencomplai.yaml` governs tool *behavior* (scan defaults, evaluator threshold
    overrides, allowlists) — it is **never** a source of compliance *declarations*.
    `system-manifest.json` (`SystemManifest`) remains the sole authority for what a
    system is declared to do. Setting `scan.fail_on: critical` in `opencomplai.yaml`
    changes when a scan gates CI; it says nothing about whether the system is actually
    compliant.

## File location

`opencomplai.yaml` is auto-discovered from `--repo-root` — place it at the root of the
repository you pass to `opencomplai scan --repo-root`. If absent, every field falls back
to its built-in default; there is no error for a missing file.

## Supported keys

Currently two keys are supported. **This list will grow** — treat any key not listed
here as unsupported in the current release.

```yaml
scan:
  fail_on: critical           # none | new-major | major | critical
  framework_detectors: true   # opt in to AST-level framework-object detection
```

| Key | Type | Overrides |
|---|---|---|
| `scan.fail_on` | string | The default for `opencomplai scan --fail-on` |
| `scan.framework_detectors` | boolean | The default for `opencomplai scan --framework-detectors` |

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

## Relationship to other config

`opencomplai.yaml` is **additive to** — not a replacement for — `.ocignore` (scan
inclusion/exclusion patterns and inventory limits, see the
[scanner guide](../getting-started/scanner.md#ocignore)) and explicit CLI flags.
Each governs a different concern:

| File / flag | Governs |
|---|---|
| `system-manifest.json` | Compliance *declaration* — `intended_purpose`, risk presumption, Annex IV fields. Sole source of truth. |
| `.ocignore` | What the scanner walks/reads — exclusion patterns, inventory limits. |
| `opencomplai.yaml` | Tool *behavior* defaults — `scan --fail-on`, `scan --framework-detectors`. |
| CLI flags | Always override both `.ocignore` defaults' equivalent settings (where applicable) and `opencomplai.yaml`. |

See [scan CLI reference](../cli/scan.md) for the full flag table these keys map onto.
