# portfolio (check with several manifests)

Check several systems in one command. This is a mode of [`check`](check.md),
not a separate command: pass `-m` / `--manifest` more than once, or a glob.

**What:** each manifest is run through the normal single-system `check`, in
order, and a failing system never stops the rest. A `portfolio-summary.json`
is written beside the per-system output.

**When:** a repository or a pipeline owns more than one AI system and each has
its own manifest.

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai check -m alpha.json -m beta.json --output-dir out
    opencomplai check --manifest "systems/*.json" --output-dir out
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check -m alpha.json -m beta.json --output-dir out
    opencomplai check --manifest "systems/*.json" --output-dir out
    ```

## Options

The mode is switched on by the number of manifests; every other `check` option
applies to each system.

| Option | Default | Description |
|---|---|---|
| `--manifest` / `-m` | `system-manifest.json` | Repeatable, one system per manifest. A value with `*`, `?` or `[` that is not an existing file is expanded by the CLI itself, so quoting works the same in PowerShell. A pattern that matches nothing exits `2`. |
| `--output-dir` | `.` | Base directory. Each system writes into a subdirectory of it. |

## Output files

```text
out/
  alpha/compliance-artifact.json     # one directory per system_id
  beta/compliance-artifact.json
  portfolio-summary.json
```

A directory is named after the `system_id` with every character outside
`A-Za-z0-9._-` replaced by `_`. A manifest whose `system_id` is missing uses
its file name without the extension.

`portfolio-summary.json` is unsigned and informational. It has no timestamp.

| Field | Meaning |
|---|---|
| `kind` | `portfolio_summary`. |
| `schema_version` | `1`. |
| `signed` | Always `false`. |
| `worst_exit_code` | The numeric maximum of the per-system exit codes. |
| `systems` | One entry per system, sorted by `system_id`. |

Each entry has `system_id`, `manifest`, `exit_code`, `result`,
`failed_controls`, `artifact` and `artifact_sha256`. `artifact` and
`artifact_sha256` are `null` when the system wrote no artifact, for example a
missing or invalid manifest; `result` is then `validation_fail` for exit `2`
and `unknown` otherwise.

With `--output json` the summary is printed, but each system also prints its
own human output, so stdout is not a single JSON document. Read
`portfolio-summary.json` for machine use.

## Rejected input

These exit `2` before any system is checked, and nothing is written:

- A manifest with a top-level `systems` key, or one that is a JSON array. One
  manifest describes one system.
- Two manifests that resolve to the same `system_id` or the same directory name.

## Exit codes

The process exits with the worst severity among the systems.

| Code | Meaning |
|---|---|
| 0 | Every system passed. |
| 1 | At least one control failed. |
| 2 | Validation: bad manifest or input. |
| 3 | A policy block. |
| 4 | A trap was hit. |

See [Exit codes](exit-codes.md) for what each code means for a single run.
[`push`](push.md) still takes one artifact at a time.
