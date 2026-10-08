# diff

Compare two compliance artifacts or gap reports: which verdicts were added, removed or changed, and whether the rules changed between the two runs. Read-only; it prints no dates.

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai diff OLD.json NEW.json [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai diff OLD.json NEW.json [OPTIONS]
    ```

## Accepted inputs

Each file can be any of:

- a `compliance-artifact.json` written by `opencomplai check --with-gaps` (it must contain a `gap_report`; an artifact without one exits 2),
- the envelope printed by `opencomplai gaps --output json`,
- a bare gap report.

The two files can be different shapes. Files written by a PowerShell or `cmd.exe` redirect are read too.

## Options

| Option | Default | Description |
|---|---|---|
| `--output`, `-o` | `human` | `human`, `json` or `markdown`. |
| `--fail-on-regression` | off | Exit 1 when any verdict got worse. |

## What counts as changed

A row is changed only when its status differs. A new rationale or confidence on the same status is not a change. Rows from every framework in the file are included (EU AI Act rows are not counted twice).

Status order, best to worst: `met`, `unverified`, `partial`, `missing`. A change to a worse status is a **regression**; a change to a better one is an improvement. Rows only in the new file are listed as added, rows only in the old file as removed; neither is a regression.

## Rule-set version

An artifact written by a recent `check` carries `rule_set_version`. When both inputs carry one, the output says whether the rules changed and lists the history entries between the two versions. When either input does not carry one (a gap report or envelope never does), the rule set is reported as unknown and nothing is claimed either way.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | No gate requested, or no regression. |
| 1 | Only with `--fail-on-regression`, when a verdict got worse. |
| 2 | An input is missing, unreadable or not a gap report. |

No new exit code; see [Exit codes](exit-codes.md).

## CI example

```bash
opencomplai check --with-gaps
opencomplai diff baseline/compliance-artifact.json compliance-artifact.json --fail-on-regression
```
