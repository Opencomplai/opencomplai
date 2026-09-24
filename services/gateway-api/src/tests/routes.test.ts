import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
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

    it('returns 422 for an empty compliance_targets list', async () => {
      const res = await app.inject({
        method: 'POST',
        url: '/v1/manifests/validate',
        payload: { system_id: 'test', intended_purpose: 'chatbot', compliance_targets: [] },
      });
      expect(res.statusCode).toBe(422);
      expect(JSON.parse(res.body).error_code).toBe('VALIDATION_ERROR');
    });

    it('forwards compliance_targets and framework_inputs to the risk engine', async () => {
      const fetchSpy: ReturnType<typeof vi.fn> = vi.fn(
        async () => new Response('{"valid":true}', { status: 200 }),
      );
      vi.stubGlobal('fetch', fetchSpy);
      const frameworkInputs = {
        NIST_AI_RMF: { excluded: { 'NIST_AI_RMF:MAP 1.1': 'Internal tool only' } },
      };
      try {
        const res = await app.inject({
          method: 'POST',
          url: '/v1/manifests/validate',
          payload: {
            system_id: 'test',
            intended_purpose: 'chatbot',
            compliance_targets: ['EU_AI_ACT', 'NIST_AI_RMF'],
            framework_inputs: frameworkInputs,
          },
        });
        expect(res.statusCode).toBe(200);
      } finally {
        vi.unstubAllGlobals();
      }
      const sentBody = JSON.parse(String(fetchSpy.mock.calls[0][1]?.body));
      expect(sentBody.compliance_targets).toEqual(['EU_AI_ACT', 'NIST_AI_RMF']);
      expect(sentBody.framework_inputs).toEqual(frameworkInputs);
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

describe('SEC-SERVICE-AUTH: HITL actor_id is bound to the verified principal', () => {
  let app: FastifyInstance;
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeAll(async () => {
    delete process.env.OPENCOMPLAI_AUTH_DISABLED;
    process.env.OPENCOMPLAI_API_KEY = 'test-secret';
    app = buildApp();
    await app.ready();
  });

  afterAll(async () => {
    await app.close();
    delete process.env.OPENCOMPLAI_API_KEY;
  });

  beforeEach(() => {
    fetchSpy = vi.fn(async () => new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('overrides a client-supplied actor_id in API-key mode', async () => {
    await app.inject({
      method: 'POST',
      url: '/v1/hitl/overrides',
      headers: { 'x-api-key': 'test-secret' },
      payload: {
        case_id: 'case-1',
        actor_id: 'attacker-forged-id',
        rationale: 'looks fine',
        decision: 'approved',
      },
    });
    const sentBody = JSON.parse(String(fetchSpy.mock.calls[0][1]?.body));
    expect(sentBody.actor_id).toBe('api-key-caller');
    expect(sentBody.actor_id).not.toBe('attacker-forged-id');
  });

  it('overrides a client-supplied reviewer_id on assign', async () => {
    await app.inject({
      method: 'POST',
      url: '/v1/hitl/queue/review-1/assign',
      headers: { 'x-api-key': 'test-secret' },
      payload: { reviewer_id: 'attacker-forged-id' },
    });
    const sentBody = JSON.parse(String(fetchSpy.mock.calls[0][1]?.body));
    expect(sentBody.reviewer_id).toBe('api-key-caller');
  });

  it('overrides a client-supplied actor_id on decide', async () => {
    await app.inject({
      method: 'POST',
      url: '/v1/hitl/queue/review-1/decide',
      headers: { 'x-api-key': 'test-secret' },
      payload: {
        actor_id: 'attacker-forged-id',
        decision: 'approved',
        rationale: 'looks fine',
      },
    });
    const sentBody = JSON.parse(String(fetchSpy.mock.calls[0][1]?.body));
    expect(sentBody.actor_id).toBe('api-key-caller');
  });
});

describe('M-05: path params are encoded before hitting upstream proxy URLs', () => {
  // Mirrors docs.ts's existing encodeURIComponent pattern; a crafted id like
  // "../overrides" must not redirect the upstream request to a sibling path.
  let app: FastifyInstance;
  let fetchSpy: ReturnType<typeof vi.fn>;

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

  beforeEach(() => {
    fetchSpy = vi.fn(async () => new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('encodes a traversal-style hitl queue id', async () => {
    await app.inject({ method: 'GET', url: '/v1/hitl/queue/..%2Foverrides' });
    const requestedUrl = String(fetchSpy.mock.calls[0][0]);
    expect(requestedUrl).toContain('/v1/hitl/queue/..%2Foverrides');
    expect(requestedUrl).not.toMatch(/\/v1\/hitl\/queue\/\.\.\/overrides$/);
  });

  it('encodes a query-metacharacter badge id without introducing a real query string', async () => {
    await app.inject({ method: 'GET', url: '/v1/pro/badges/verify/abc%3Fx%3D1' });
    const requestedUrl = String(fetchSpy.mock.calls[0][0]);
    expect(requestedUrl).toContain('/v1/pro/badges/verify/abc%3Fx%3D1');
    // A raw '?' here would let the crafted id inject query params / change what
    // the upstream service receives — confirm no unescaped '?' made it through.
    expect(requestedUrl.split('?')).toHaveLength(1);
  });
});
