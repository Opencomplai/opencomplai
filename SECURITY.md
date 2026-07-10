# Security Policy

## Reporting a vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report
it responsibly.

**Do not create a public GitHub issue for security vulnerabilities.**

Instead, email **security@opencomplai.com** with:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes (optional)

### Response timeline

We aim to acknowledge reports within 48 hours and to provide a remediation timeline:

| Severity | Acknowledgement | Fix target |
|---|---|---|
| Critical | 24 hours | 7 days |
| High | 48 hours | 14 days |
| Medium | 7 days | 30 days |
| Low | 30 days | Next release |

### Scope

In scope:

- `opencomplai-core` — risk assessment engine (Python)
- `opencomplai-cli` — command-line interface (Python)
- `opencomplai` — Python SDK
- The services under `services/` (gateway-api, risk-engine, evidence-vault, doc-generator, egress-proxy)

Out of scope:

- Social engineering
- Physical security
- Third-party dependencies (please report upstream)
- Deployments operated by end users

### Disclosure policy

We follow coordinated disclosure:

1. The reporter notifies us privately.
2. We develop and test a fix.
3. We publish the fix and a security advisory, crediting the reporter.

## Security controls

For users:

- Releases are signed with Ed25519 (see `packages/core/src/opencomplai_core/signing.py`).
- A Software Bill of Materials (SBOM) is published with releases.
- Dependency vulnerability scanning runs in CI (`pip-audit` / `npm audit`).

For contributors:

- All code contributions require review.
- No secrets in code (enforced by pre-commit and CI).
- Signed commits are recommended.
