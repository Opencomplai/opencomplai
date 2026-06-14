import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { FastifyInstance } from 'fastify';
import { buildApp } from '../index';

describe('Gateway API routes', () => {
  let app: FastifyInstance;

  beforeAll(async () => {
    delete process.env.OPENCOMPLAI_API_KEY;
    process.env.OPENCOMPLAI_AUTH_DISABLED = '1';
    app = buildApp();
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
    delete process.env.OPENCOMPLAI_AUTH_DISABLED;
  });

  describe('GET /health', () => {
    it('returns 200 with status ok', async () => {
      const res = await app.inject({ method: 'GET', url: '/health' });
      expect(res.statusCode).toBe(200);
      expect(JSON.parse(res.body).status).toBe('ok');
    });
  });

  describe('POST /v1/manifests/validate', () => {
    it('returns 422 for missing system_id', async () => {
      const res = await app.inject({
        method: 'POST',
        url: '/v1/manifests/validate',
        payload: { intended_purpose: 'test' },
      });
      expect(res.statusCode).toBe(422);
      const body = JSON.parse(res.body);
      expect(body.error_code).toBe('VALIDATION_ERROR');
    });

    it('returns 503 when risk-engine is unavailable', async () => {
      process.env.RISK_ENGINE_URL = 'http://localhost:19999';
      const res = await app.inject({
        method: 'POST',
        url: '/v1/manifests/validate',
        payload: {
          system_id: 'test',
          intended_purpose: 'chatbot',
          compliance_target: 'EU_AI_ACT',
          high_risk_presumption: false,
          commit_ref: 'HEAD',
        },
      });
      expect(res.statusCode).toBe(503);
      expect(JSON.parse(res.body).error_code).toBe('DEPENDENCY_UNAVAILABLE');
    });
  });

  describe('GET /v1/docs', () => {
    it('returns 422 when system_id is missing', async () => {
      const res = await app.inject({ method: 'GET', url: '/v1/docs' });
      expect(res.statusCode).toBe(422);
      expect(JSON.parse(res.body).error_code).toBe('VALIDATION_ERROR');
    });

    it('returns 503 when doc-generator is unavailable', async () => {
      process.env.DOC_GENERATOR_URL = 'http://localhost:19999';
      const res = await app.inject({
        method: 'GET',
        url: '/v1/docs?system_id=test-system',
      });
      expect(res.statusCode).toBe(503);
      expect(JSON.parse(res.body).error_code).toBe('DEPENDENCY_UNAVAILABLE');
    });
  });

  describe('GET /v1/docs/:dossier_id', () => {
    it('returns 503 when doc-generator is unavailable', async () => {
      process.env.DOC_GENERATOR_URL = 'http://localhost:19999';
      const res = await app.inject({
        method: 'GET',
        url: '/v1/docs/abc-123',
      });
      expect(res.statusCode).toBe(503);
      expect(JSON.parse(res.body).error_code).toBe('DEPENDENCY_UNAVAILABLE');
    });
  });

  describe('GET /v1/evidence/verify-chain', () => {
    it('returns 503 when evidence-vault is unavailable', async () => {
      process.env.EVIDENCE_VAULT_URL = 'http://localhost:19999';
      const res = await app.inject({
        method: 'GET',
        url: '/v1/evidence/verify-chain',
      });
      expect(res.statusCode).toBe(503);
      expect(JSON.parse(res.body).error_code).toBe('DEPENDENCY_UNAVAILABLE');
    });
  });

  describe('POST /v1/hitl/overrides', () => {
    it('returns 422 when rationale is empty', async () => {
      const res = await app.inject({
        method: 'POST',
        url: '/v1/hitl/overrides',
        payload: {
          case_id: 'case-1',
          actor_id: 'user-1',
          rationale: '',
          decision: 'approved',
        },
      });
      expect(res.statusCode).toBe(422);
      expect(JSON.parse(res.body).error_code).toBe('VALIDATION_ERROR');
    });
  });
});

describe('Gateway API auth middleware', () => {
  it('allows /health without API key', async () => {
    process.env.OPENCOMPLAI_API_KEY = 'test-key';
    const app = buildApp();
    await app.ready();
    const res = await app.inject({ method: 'GET', url: '/health' });
    await app.close();
    expect(res.statusCode).toBe(200);
  });

  it('returns 401 without header when API key is set', async () => {
    process.env.OPENCOMPLAI_API_KEY = 'test-key';
    const app = buildApp();
    await app.ready();
    const res = await app.inject({ method: 'GET', url: '/v1/status' });
    await app.close();
    expect(res.statusCode).toBe(401);
    expect(JSON.parse(res.body).error_code).toBe('POLICY_DENIED');
  });
});
