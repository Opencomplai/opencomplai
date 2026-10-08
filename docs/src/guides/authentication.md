# Authentication

## Fail-closed by default

The gateway API authenticates every non-health request and fails closed: it refuses to start unless you configure one of two supported authentication modes, or explicitly opt out for local development.

| Mode | When to use | Env var |
|---|---|---|
| API-key | Self-hosted, single-operator | `OPENCOMPLAI_API_KEY` |
| OIDC JWT | Multi-user / SaaS | `OIDC_JWKS_URI` |

If neither variable is set, the gateway logs `Gateway refusing to start: OPENCOMPLAI_API_KEY is not set...` and exits rather than accepting unauthenticated traffic. The only way to run without auth is to explicitly set `OPENCOMPLAI_AUTH_DISABLED=1`, which is meant for local development only and is not safe for production use.

For the full configuration steps, environment variables, and identity-provider examples, see [Deployment › Authentication](../deployment/authentication.md).

## Dashboard authentication (Premium)

The Opencomplai Premium Dashboard uses email/password or magic-link authentication for the tenant web UI. The CLI uses one-time bootstrap tokens for the `dashboard enroll` command. See [dashboard enroll](../cli/dashboard.md) for details.

## Signing for CI authenticity

To prove that a compliance artifact was produced by a known install (not forged), use `--sign`:

=== "macOS / Linux"
    ```bash
    opencomplai check --sign
    ```

=== "Windows (PowerShell)"
    ```powershell
    opencomplai check --sign
    ```

This signs the `ScanStatusArtifact` with the Ed25519 key in `~/.opencomplai/signing.key`, or with the key in the `SIGNING_KEY_PRIVATE` environment variable (base64-encoded PEM) when it is set, which suits CI where no key file exists. The signature can be verified by anyone who has the corresponding public key (`~/.opencomplai/signing.pub`).

If neither key exists, `check --sign` exits `2` and writes no artifact. To sign when a key is present and carry on unsigned (with a warning) when it is not, use `opencomplai check --sign-if-available`.
