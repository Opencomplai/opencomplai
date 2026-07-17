# `opencomplai report`

Render a single shareable HTML or PDF document combining the manifest, rule results, a
gap report, and eval/scan summaries — a human-readable snapshot to hand to a
stakeholder who doesn't want to read raw JSON.

!!! tip "Read-only, no network, no second CI gate"
    `report` only reads already-local files (`--manifest`, `--artifact`,
    `--gap-report`) and makes no network calls. It is **not** a replacement for the
    Annex IV dossier (`opencomplai docs generate`) and does **not** carry its own exit
    code contract — the CI gate stays exclusively with `opencomplai check`.

## Usage

=== "macOS / Linux"
    ```bash
    opencomplai report --manifest system-manifest.json --output report.html
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai report --manifest system-manifest.json --output report.html
    ```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--manifest` / `-m` | `system-manifest.json` | System manifest path |
| `--artifact` | `compliance-artifact.json` | Path to a `ScanStatusArtifact` (from `opencomplai check`) — optional; supplies rule results and, if present, embedded `gap_report`/`eval_summary`/`scan_summary` |
| `--gap-report` | *(none)* | Path to a `GapReport` JSON — overrides any `gap_report` embedded in `--artifact` |
| `--output` / `-o` | `report.html` | Output path — format is inferred from the file extension |

## HTML vs. PDF

The output format is inferred purely from `--output`'s file extension — there is no
separate `--format` flag:

=== "macOS / Linux"
    ```bash
    # HTML (self-contained, styled)
    opencomplai report --manifest system-manifest.json --output report.html

    # PDF (requires the optional 'reports' extra — fpdf2 >= 2.7)
    opencomplai report --manifest system-manifest.json --output report.pdf
    ```

=== "Windows (PowerShell)"
    ```powershell
    # HTML (self-contained, styled)
    opencomplai report --manifest system-manifest.json --output report.html

    # PDF (requires the optional 'reports' extra — fpdf2 >= 2.7)
    opencomplai report --manifest system-manifest.json --output report.pdf
    ```

The PDF path reuses the same `fpdf2`-based renderer already used elsewhere in the
product for PDF export — there is no second PDF toolchain to install or maintain.

## Getting the richest report

`report` fills in whatever sections it has data for and prints an explanatory
placeholder for anything missing (e.g. *"No gap report supplied — run `opencomplai
gaps` first."*). For the fullest document, generate the gap report and the
compliance artifact first:

=== "macOS / Linux"
    ```bash
    opencomplai check --with-gaps --scan
    opencomplai report --manifest system-manifest.json --artifact compliance-artifact.json --output report.html
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check --with-gaps --scan
    opencomplai report --manifest system-manifest.json --artifact compliance-artifact.json --output report.html
    ```

`check --with-gaps` attaches a `gap_report` directly to `compliance-artifact.json`
(additive, informational only — it does not change `check`'s exit code), so a single
artifact file is enough input for `report` to render every section: rule results, gap
report, eval summary, and scan summary.

## Report sections

| Section | Populated from | If missing |
|---|---|---|
| Rule results | `risk_result` (always computed from `--manifest`) | n/a — always present |
| Gap report table | `--gap-report`, or `--artifact`'s embedded `gap_report` | *"No gap report supplied — run `opencomplai gaps` first."* |
| Eval summary | `--artifact`'s embedded `eval_summary` | *"No eval summary supplied — run with `--sample-set`."* |
| Scan summary | `--artifact`'s embedded `scan_summary` | *"No scan summary supplied — run with `--scan`."* |

See [gaps](gaps.md) and [recommend](recommend.md) for the commands that produce the gap
report this feeds from.
