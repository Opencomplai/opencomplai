# `opencomplai scope`

Answer a framework pack's scope questions and see which requirements the answers take out.

**What:** asks the yes/no applicability and scope questions a pack declares, writes the
answers to `framework_inputs.<KEY>.scope` in the manifest, and prints the framework
outcome and the rows the answers take out of the report.

**When:** after `opencomplai init`, once you target a framework other than the EU AI Act
and want requirements that do not apply to your system to leave its gap report.

**Don't:** use it for `EU_AI_ACT`. That framework has no scope questions and the command
exits 2; use [checker](checker.md) for its applicability checker.

## Usage

=== "macOS / Linux"
    ```bash
    opencomplai scope ISO_IEC_27090 --manifest system-manifest.json
    opencomplai scope ISO_IEC_27090 --answer trains_models=no --answer public_api=yes
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai scope ISO_IEC_27090 --manifest system-manifest.json
    opencomplai scope ISO_IEC_27090 --answer trains_models=no --answer public_api=yes
    ```

On a terminal, the command prompts for each question you did not answer with `--answer`;
an empty reply leaves that question unanswered. Without a terminal, or with
`--output json`, it does not prompt.

### Arguments and options

| Flag | Default | Description |
|------|---------|-------------|
| `FRAMEWORK` | required | Framework key, for example `ISO_IEC_27090` |
| `--manifest` | `system-manifest.json` | Manifest to update. A missing or invalid file exits 2 |
| `--answer` | none | `KEY=yes` or `KEY=no`; repeatable. Skips the prompt for that key. An unknown key or value exits 2 |
| `--output` / `-o` | `human` | `human` or `json` |

## Outputs

The manifest is rewritten with the answers under `framework_inputs.<KEY>.scope`. The
command then prints the framework outcome, if the pack has one, and the number of
requirements that are out of scope with a reason for each. With `--output json` it prints
`framework`, `outcome`, `reason`, `scope` and `scoped_out`.

## Next step

Run [gaps](gaps.md) to see the report without the rows the answers took out.
