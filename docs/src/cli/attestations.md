# attestations

Download the attestation bundle for a system and write it to a file.

**What:** `attestations pull` fetches the signed bundle of an organisation's attestations and exclusions from the
endpoint configured in `OPENCOMPLAI_DASHBOARD_URL`, the endpoint [`push`](push.md) uploads to, and writes it as
pretty-printed JSON. The format and the merge rules are on
[More framework packs](../frameworks/more-packs.md#attestation-bundles).

**When:** in a CI job that should be reproducible. Pull the bundle once, keep the file, and give it to
[`check`](check.md) with `--attestations-file`, so the run reads the same bytes every time and makes no network
call. `check`, `gaps`, `recommend` and `docs generate` can also fetch the bundle themselves with
`--attestations-remote`.

**Requires:** two environment variables, the pair `push` uses.

| Variable | Meaning |
|---|---|
| `OPENCOMPLAI_API_KEY` | An `ock_...` key. |
| `OPENCOMPLAI_DASHBOARD_URL` | The base URL of the endpoint, for example `https://app.opencomplai.com/api/ingest`. The request goes to `<URL>/v1/attestations`. |

If either is unset, or the key contains a space, a newline or a non-ASCII character, `pull` exits `3` before sending
anything, and the key is never printed. Unlike `push`, which only warns, `pull` refuses a
plain `http` URL to any host other than `localhost`, `127.0.0.1` or `::1`, because the API key would travel
unencrypted. It never follows a redirect, and it refuses a response larger than 2 MiB.

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai attestations pull -o FILE [--system-id ID]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai attestations pull -o FILE [--system-id ID]
    ```

## Options

| Option | Default | Description |
|---|---|---|
| `--output` / `-o` | *(required)* | File to write the bundle to. Missing folders are created. |
| `--system-id` | *(none)* | The system the bundle is for (the manifest's `system_id`). Without it the bundle holds the organisation-wide records only. |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | The bundle was fetched, validated and written. |
| `3` | Anything else: a variable is unset or the key cannot be sent, the URL is refused, the endpoint could not be reached or answered with an error, the response is not a valid bundle, or the file could not be written. Nothing is written. |

`pull` never changes a gate: it is a separate step, so a network failure cannot change the verdict of `check`.

For a job that gates the build, pull the bundle in its own step and give `check` the file with
`--attestations-file`. `check --attestations-remote` asks the endpoint itself, and when the endpoint is down the rows
the bundle attested read Unverified again, which can fail `--gate-fail-on unverified`.

A pulled file is a snapshot: it holds the records as they were when it was issued (see `issued_at`), so a record
withdrawn or renewed afterwards is not seen until you pull again. Pull on every run, or on a schedule, rather than
keeping one file for good. Each record's own `valid_until` still applies.

## Examples

Pull the bundle for one system, then check against the saved file.

=== "macOS / Linux"
    ```bash
    export OPENCOMPLAI_API_KEY=ock_...
    export OPENCOMPLAI_DASHBOARD_URL=https://app.opencomplai.com/api/ingest
    opencomplai attestations pull -o attestations.json --system-id loan-decision-model
    opencomplai check --with-gaps --attestations-file attestations.json
    ```

=== "Windows (PowerShell)"
    ```powershell
    $env:OPENCOMPLAI_API_KEY = "ock_..."
    $env:OPENCOMPLAI_DASHBOARD_URL = "https://app.opencomplai.com/api/ingest"
    opencomplai attestations pull -o attestations.json --system-id loan-decision-model
    opencomplai check --with-gaps --attestations-file attestations.json
    ```
