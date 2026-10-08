# `opencomplai instructions generate`

Draft the Art. 13(3) instructions for use from your system manifest: one row for each of
the 13 points, with the content the manifest holds and an explicit **not captured** marker
for everything it does not.

**What:** an instructions-for-use pack as JSON and Markdown.

**When:** before you hand a high-risk system to a deployer, or when `opencomplai gaps`
shows Art. 13 as Missing or Partial.

**Don't:** treat the output as legal advice or as a finished document. It is an
informational draft. Every point and legal reference is flagged `needs_founder_review`
with `medium` confidence, because the point list is an unchecked reading of Art. 13(3).

`opencomplai recommend` now writes the instructions-for-use skeleton
(`art13-instructions_for_use.md`) for Art. 13, instead of the Art. 50 disclosure stub it
wrote before.

## Usage

=== "macOS / Linux"
    ```bash
    opencomplai instructions generate --manifest system-manifest.json
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai instructions generate --manifest system-manifest.json
    ```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--manifest` / `-m` | `system-manifest.json` | System manifest. A missing or invalid file exits 2 |
| `--output-dir` | `./instructions-for-use` | Directory for `instructions_for_use.json` and `instructions_for_use.md` |
| `--output` / `-o` | `human` | `human` or `json` |

The default directory is deliberately not `docs/` and not named `instructions*`, so an
unfilled draft is never read as evidence for the Art. 13 file probe in `opencomplai gaps`.

## The 13 points

| Point | Element | Manifest field |
|---|---|---|
| (a) | Provider identity and contact details | `provider_contact` |
| (b)(i) | Intended purpose | `intended_purpose` |
| (b)(ii) | Accuracy, robustness and cybersecurity levels | `performance_metrics`, `metrics_appropriateness_rationale` |
| (b)(ii) | Known limitations | `known_limitations` |
| (b)(iii) | Known or foreseeable circumstances leading to risk | `foreseeable_misuse` |
| (b)(iv) | Capabilities to explain outputs | *none: always not captured* |
| (b)(v) | Performance for specific persons or groups | *none: always not captured* |
| (b)(vi) | Input-data specifications | `input_data_specifications` |
| (b)(vii) | Information to interpret the output | *none: always not captured* |
| (c) | Pre-determined changes | `predetermined_changes` |
| (d) | Human oversight measures | `human_oversight_measures` |
| (e) | Lifetime and maintenance | `expected_lifetime_and_maintenance` |
| (f) | Log mechanisms and interpretation | `log_interpretation` |

At most 10 of the 13 points can be populated from the manifest.

## New manifest fields

Six optional fields, all omitted from the written manifest when unset, so existing
manifests keep the same bytes:

| Field | Type | Art. 13(3) point |
|---|---|---|
| `provider_contact` | text | (a) |
| `foreseeable_misuse` | list of text | (b)(iii) |
| `input_data_specifications` | text | (b)(vi) |
| `predetermined_changes` | list of text | (c) |
| `expected_lifetime_and_maintenance` | text | (e) |
| `log_interpretation` | text | (f) |
