# `opencomplai scaffold`

Write a framework pack's fill-in documents.

**What:** copies the pack's scaffolds, starting-point documents with `_fill in_`
placeholders, into your project, one file per document.

**When:** when a gap report names a document the framework expects and you have none yet.

**Don't:** treat a scaffold as finished evidence. It is a skeleton; the content is yours to
write.

## Usage

=== "macOS / Linux"
    ```bash
    opencomplai scaffold ISO_IEC_42001 --list
    opencomplai scaffold ISO_IEC_42001 --output-dir ./docs
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scaffold ISO_IEC_42001 --list
    opencomplai scaffold ISO_IEC_42001 --output-dir ./docs
    ```

Pass a document id after the framework key to write one document instead of all of them.

### Arguments and options

| Flag | Default | Description |
|------|---------|-------------|
| `FRAMEWORK` | required | Framework key, for example `ISO_IEC_42001` |
| `DOC` | every document | Document id. An unknown id exits 2 |
| `--list` | off | List document ids, titles and targets; write nothing |
| `--output-dir` | `.` | Directory the targets are written under |
| `--force` | off | Overwrite existing files. Without it, an existing file is skipped |
| `--output` | `human` | `human` or `json` |

An unknown framework, or a framework that ships no scaffolds, exits 2.

## Outputs

Each document is written to its target path under `--output-dir`. The command prints
`created <path>` or `skipped <path> (exists; use --force)` for each; with `--output json` it
prints `framework`, `created` and `skipped`. With `--list --output json` it prints the
`documents`, each with `id`, `title` and `target`.

## Next step

Fill in the placeholders, then run [gaps](gaps.md) again.
