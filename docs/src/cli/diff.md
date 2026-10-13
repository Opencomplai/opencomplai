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

## Tool changed

An artifact also records which tool wrote it. When both inputs carry the same field, `diff` compares `cli_version`, `rule_set_version` and `scan_summary.scanner_version`, and prints a "Tool changed" block listing each field that differs as `field: from -> to`. A field present on only one side is not compared. A gap report or envelope carries none of these, so nothing is claimed.

When a verdict got worse and the tool also changed, the output adds a note that the worse verdict may come from the upgrade rather than from your code. The note never changes the exit code.

JSON output gains an additive `tool_changes` field; every other key is unchanged:

```json
{"changed": true, "fields": [{"field": "cli_version", "from": "0.9.0", "to": "0.9.1"}]}
```

`changed` is `null` when no field could be compared, and `fields` is then empty. Detector versions are not recorded in artifacts, so they are not shown.

`scanner_version` identifies the scanner engine only. The signal dictionary and the scope classifier carry their own versions, named in the release notes, so findings can change between releases while `scanner_version` stays the same. `cli_version` is the field that reveals an upgrade.

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
