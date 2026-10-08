# Webhooks

Webhooks are not implemented in this release.

For event-driven integration, use the evidence ledger's event stream via `POST /v1/evidence/events` to append events, and poll the ledger via `GET /v1/evidence/verify-chain` to consume them.

Webhook delivery is on the roadmap for a future release. Watch the [GitHub repository](https://github.com/Opencomplai/opencomplai) for updates.
