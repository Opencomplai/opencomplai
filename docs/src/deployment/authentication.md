# Authentication Configuration

**Compliance mapping:** ISO 27001 A.8.5 · SOC 2 CC6.1 · NIST PR.AA · FedRAMP IA-2

---

## Two Authentication Modes

| Mode | When to use | Env var |
|---|---|---|
| API-key | Self-hosted, single-operator | `OPENCOMPLAI_API_KEY` |
| OIDC JWT | Multi-user / SaaS | `OIDC_JWKS_URI` |

`OIDC_JWKS_URI` takes priority. When set, `OPENCOMPLAI_API_KEY` is ignored.

---

## API-Key Mode (Self-Hosted)

=== "macOS / Linux"
    ```bash
    OPENCOMPLAI_API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
    ```

=== "Windows (PowerShell)"
    ```powershell
    $env:OPENCOMPLAI_API_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
    ```

All non-health requests must carry `x-api-key: <key>`.

---

## OIDC JWT Mode (Multi-User / SaaS)

```bash
# Auth0
OIDC_JWKS_URI=https://your-tenant.auth0.com/.well-known/jwks.json
# Entra ID
OIDC_JWKS_URI=https://login.microsoftonline.com/<tenant>/discovery/v2.0/keys
```

All requests must carry `Authorization: Bearer <jwt>`. The gateway verifies the JWT signature against the JWKS endpoint.

For production, replace the built-in verifier in `services/gateway-api/src/middleware/auth.ts` with `jose` or `jsonwebtoken + jwks-rsa`.

---

## MFA Enforcement

Enforce MFA for admin-role users at the IdP level, not in application code. Configure an MFA policy in your IdP (Auth0 Actions, Entra Conditional Access, Cognito MFA) before connecting to production.

---

## Local Development Only

```bash
OPENCOMPLAI_AUTH_DISABLED=1   # NEVER in production
```
