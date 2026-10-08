# rules changelog

Show the rule-set history: what changed in each version of the rules that produce your verdicts. Read-only.

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai rules changelog [OPTIONS]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai rules changelog [OPTIONS]
    ```

## Options

| Option | Default | Description |
|---|---|---|
| `--since`, `-s` | *(all)* | Only versions newer than this one, for example `1.5.0`. Compared numerically, so `1.10.0` is newer than `1.9.0`. A value that is not a dotted version exits 2. |
| `--output`, `-o` | `human` | `human`, `json` or `markdown`. |

Entries are printed oldest to newest, so the last one is the current rule-set version.

## Provenance

Each entry shows three fields exactly as stored:

- `source`: where the change description comes from,
- `confidence`: how sure the entry is,
- `needs_founder_review`: shown as "needs founder review" when true.

The `json` output prints the stored entries unchanged. To see what changed between two of your runs, use [diff](diff.md).
