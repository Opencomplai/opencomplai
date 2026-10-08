# push

Publish a signed artifact to the Opencomplai Premium Dashboard.

**What:** sends one file, either the scan status written by [`check`](check.md)
or an Annex IV dossier written by [`docs generate`](docs-generate.md), to the
dashboard's ingest endpoint.

**When:** as a separate step after `check` has already gated the build locally.
`push` is deliberately not a flag on `check`, so a network failure can never
change a CI gate.

**Requires:** two environment variables.

| Variable | Meaning |
|---|---|
| `OPENCOMPLAI_API_KEY` | An `ock_...` key issued by the dashboard. |
| `OPENCOMPLAI_DASHBOARD_URL` | The dashboard's ingest base URL, for example `https://app.opencomplai.com/api/ingest`. |

If either is unset, `push` exits `3` before sending anything. A plain `http`
URL to a host other than `localhost` or `127.0.0.1` prints a warning, because
the API key would travel unencrypted.

## Synopsis

=== "macOS / Linux"
    ```bash
    opencomplai push [ARTIFACT_FILE] [--kind scan-status|dossier-envelope]
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai push [ARTIFACT_FILE] [--kind scan-status|dossier-envelope]
    ```

## Options

| Option | Default | Description |
|---|---|---|
| `ARTIFACT_FILE` | see below | Path to the file to publish. |
| `--kind` | `scan-status` | Which shape to publish: `scan-status` or `dossier-envelope`. |

Default file when `ARTIFACT_FILE` is omitted:

- `--kind scan-status`: `compliance-artifact.json` in the current directory.
- `--kind dossier-envelope`: the most recently modified `dossier_*.json` in the
  current directory. If there is none, `push` exits `3` and tells you to run
  `opencomplai docs generate` first.

A file that is missing, unreadable, not valid JSON, or not a JSON object also
exits `3`, with a one-line message on stderr.

## Examples

Publish the scan status that `check --sign` just wrote.

=== "macOS / Linux"
    ```bash
    export OPENCOMPLAI_API_KEY=ock_...
    export OPENCOMPLAI_DASHBOARD_URL=https://app.opencomplai.com/api/ingest
    opencomplai check --sign
    opencomplai push
    ```

=== "Windows (PowerShell)"
    ```powershell
    $env:OPENCOMPLAI_API_KEY = "ock_..."
    $env:OPENCOMPLAI_DASHBOARD_URL = "https://app.opencomplai.com/api/ingest"
    opencomplai check --sign
    opencomplai push
    ```

Publish the newest dossier.

=== "macOS / Linux"
    ```bash
    opencomplai docs generate --system-id loan-decision-model
    opencomplai push --kind dossier-envelope
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai docs generate --system-id loan-decision-model
    opencomplai push --kind dossier-envelope
    ```

On success `push` prints the outcome (`accepted`, or `replayed` when the
dashboard already holds identical content), the `system_id` and the
`content_hash` it returned.

## What is sent

- **Scan status:** the artifact is reshaped for ingest and sent with its own
  signature only when the reshaped payload is byte-identical to what was
  signed. Otherwise the signature is left out and `push` prints a note: the API
  key then attests the push.
- **Dossier:** the envelope's signature is always empty. The dossier's own
  signature covers the dossier bundle under a different scheme, so it is not
  forwarded.

No `install_id` is sent in either case; the dashboard derives the project from
the API key.

## Exit codes

`push` has its own contract and never reflects the scan verdict.

| Code | Meaning |
|---|---|
| 0 | The dashboard answered HTTP 200 or 201. |
| 3 | Anything else: unset environment variables, missing or unreadable file, no dossier found, or a non-success answer from the dashboard. |

A `check` that failed the gate still pushes with exit `0` if the dashboard
accepts it. See [Exit codes](exit-codes.md) for the contract of the other
commands.

## See also

- [check](check.md): writes `compliance-artifact.json`.
- [docs generate](docs-generate.md): writes `dossier_<id>.json`.
- [dashboard](dashboard.md): enrol this install in the dashboard.
