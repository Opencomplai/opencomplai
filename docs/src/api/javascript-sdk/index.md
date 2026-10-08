# JavaScript/TypeScript SDK

No JavaScript/TypeScript SDK ships in this release.

For JavaScript/TypeScript integration, call the [Gateway API REST Reference](../rest-api.md) directly. All endpoints accept and return JSON. The gateway authenticates every non-health request by default — send an `x-api-key` header (API-key mode) or an `Authorization: Bearer <jwt>` header (OIDC mode); see [Authentication](../../deployment/authentication.md) for how to configure and obtain credentials.

## Direct REST API usage (TypeScript example)

```typescript
// Health check (no authentication required)
const health = await fetch('http://localhost:8080/health').then(r => r.json());
// { status: 'ok', service: 'gateway-api', version: '0.9.0' }

// Risk classification (requires an API key)
const risk = await fetch('http://localhost:8080/v1/risk/classify', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'x-api-key': '<your-api-key>',
  },
  body: JSON.stringify({
    system_id: 'my-model',
    intended_purpose: 'customer support chatbot',
  }),
}).then(r => r.json());
// { risk_class: 'limited', trap_detected: false, ... }
```

A TypeScript SDK is on the roadmap. Watch the [GitHub repository](https://github.com/Opencomplai/opencomplai) for updates.
