# Authentication

## No API key model (by design)

Opencomplai does **not** use API keys, `Authorization` headers, or JWT tokens in the OSS gateway API. The Docker Compose stack runs within your own infrastructure and trusts callers on the local network by design.

This is intentional: the OSS compliance toolkit is a local/CI tool. Access control is provided by:

1. **Network isolation** — the gateway API (`localhost:8080`) should not be exposed to the public internet.
2. **Signing keypairs** — artifact authenticity is proven by Ed25519 signatures, not by API-level auth.
3. **Egress allowlist** — outbound traffic is restricted to declared destinations by the egress proxy.

## Dashboard authentication (Premium)

The Opencomplai Premium Dashboard uses email/password or magic-link authentication for the tenant web UI. The CLI uses one-time bootstrap tokens for the `dashboard enroll` command. See [dashboard enroll](../cli/dashboard.md) for details.

## Signing for CI authenticity

To prove that a compliance artifact was produced by a known install (not forged), use `--sign`:

```bash
opencomplai check --sign
```

This signs the `ScanStatusArtifact` with the Ed25519 key in `~/.opencomplai/signing.key`. The signature can be verified by anyone who has the corresponding public key (`~/.opencomplai/signing.pub`).
