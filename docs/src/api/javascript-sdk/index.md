# JavaScript/TypeScript SDK

A JavaScript/TypeScript SDK for Opencomplai is not yet available in v0.1.

For JavaScript/TypeScript integration, call the [Gateway API REST Reference](../rest-api.md) directly. All endpoints accept and return JSON and require no authentication in the OSS Docker Compose deployment.

## Direct REST API usage (TypeScript example)

```typescript
// Health check
const health = await fetch('http://localhost:8080/health').then(r => r.json());
// { status: 'ok', service: 'gateway-api', version: '0.1.0-dev' }

// Risk classification
const risk = await fetch('http://localhost:8080/v1/risk/classify', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    system_id: 'my-model',
    intended_purpose: 'customer support chatbot',
  }),
}).then(r => r.json());
// { risk_class: 'limited', trap_detected: false, ... }
```

A TypeScript SDK is on the roadmap. Watch the [GitHub repository](https://github.com/Opencomplai/opencomplai) for updates.
