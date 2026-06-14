import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { buildApp } from '../index';

describe('Gateway authentication contract', () => {
  const originalApiKey = process.env.OPENCOMPLAI_API_KEY;
  const originalAuthDisabled = process.env.OPENCOMPLAI_AUTH_DISABLED;

  beforeEach(() => {
    delete process.env.OPENCOMPLAI_API_KEY;
    delete process.env.OPENCOMPLAI_AUTH_DISABLED;
  });

  afterEach(() => {
    if (originalApiKey === undefined) {
      delete process.env.OPENCOMPLAI_API_KEY;
    } else {
      process.env.OPENCOMPLAI_API_KEY = originalApiKey;
    }
    if (originalAuthDisabled === undefined) {
      delete process.env.OPENCOMPLAI_AUTH_DISABLED;
    } else {
      process.env.OPENCOMPLAI_AUTH_DISABLED = originalAuthDisabled;
    }
  });

  it('refuses to start when no API key is set and auth is not explicitly disabled', () => {
    // Default-deny: the launch blocker we are closing.
    expect(() => buildApp()).toThrow(/OPENCOMPLAI_API_KEY/);
  });

  it('starts open when OPENCOMPLAI_AUTH_DISABLED=1 (dev/CI escape hatch)', async () => {
    process.env.OPENCOMPLAI_AUTH_DISABLED = '1';
    const app = buildApp();
    await app.ready();
    try {
      const res = await app.inject({ method: 'GET', url: '/health' });
      expect(res.statusCode).toBe(200);
    } finally {
      await app.close();
    }
  });

  it('rejects unauthenticated requests when an API key is set', async () => {
    process.env.OPENCOMPLAI_API_KEY = 'test-secret';
    const app = buildApp();
    await app.ready();
    try {
      // /health stays open even with auth on, so the assertion targets a real route.
      const res = await app.inject({
        method: 'POST',
        url: '/v1/manifests/validate',
        payload: { system_id: 'x', intended_purpose: 'y' },
      });
      expect(res.statusCode).toBe(401);
      expect(JSON.parse(res.body).error_code).toBe('POLICY_DENIED');
    } finally {
      await app.close();
    }
  });

  it('accepts requests carrying the correct x-api-key header', async () => {
    process.env.OPENCOMPLAI_API_KEY = 'test-secret';
    // Point at a black hole so the response is a deterministic 503 rather than
    // flakily hitting whatever happens to be listening on 8001.
    process.env.RISK_ENGINE_URL = 'http://localhost:19999';
    const app = buildApp();
    await app.ready();
    try {
      const res = await app.inject({
        method: 'POST',
        url: '/v1/manifests/validate',
        headers: { 'x-api-key': 'test-secret' },
        payload: {
          system_id: 'x',
          intended_purpose: 'y',
          compliance_target: 'EU_AI_ACT',
          high_risk_presumption: false,
          commit_ref: 'HEAD',
        },
      });
      // Auth passed; failure must be the dependency, not the key check.
      expect(res.statusCode).toBe(503);
      expect(JSON.parse(res.body).error_code).toBe('DEPENDENCY_UNAVAILABLE');
    } finally {
      await app.close();
    }
  });
});
