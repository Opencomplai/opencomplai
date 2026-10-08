import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { FastifyInstance } from 'fastify';
import { buildApp } from '../index';

describe('HITL second approval', () => {
  let app: FastifyInstance;
  let fetchSpy: ReturnType<typeof vi.fn>;
  const headers = { 'x-api-key': 'test-secret' };
  const ok = { rationale: 'second look', rationale_hash: 'sha256:abc' };

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
    fetchSpy = vi.fn(async () => new Response('{}', { status: 201 }));
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('forwards requires_dual_approval on submit', async () => {
    await app.inject({
      method: 'POST',
      url: '/v1/hitl/overrides',
      headers,
      payload: {
        case_id: 'c1',
        actor_id: 'a',
        rationale: 'r',
        decision: 'approved',
        requires_dual_approval: true,
      },
    });
    expect(JSON.parse(String(fetchSpy.mock.calls[0][1]?.body)).requires_dual_approval).toBe(true);
  });

  it('binds actor_id to the principal on second approval', async () => {
    await app.inject({
      method: 'POST',
      url: '/v1/hitl/overrides/ov-1/second-approval',
      headers,
      payload: { actor_id: 'attacker-forged-id', ...ok },
    });
    expect(String(fetchSpy.mock.calls[0][0])).toContain('/v1/hitl/overrides/ov-1/second-approval');
    const sent = JSON.parse(String(fetchSpy.mock.calls[0][1]?.body));
    expect(sent.actor_id).toBe('api-key-caller');
    expect(sent.decision).toBe('approved');
  });

  it('422 on empty rationale', async () => {
    const res = await app.inject({
      method: 'POST',
      url: '/v1/hitl/overrides/ov-1/second-approval',
      headers,
      payload: { actor_id: 'b', ...ok, rationale: '' },
    });
    expect(res.statusCode).toBe(422);
    expect(JSON.parse(res.body).error_code).toBe('VALIDATION_ERROR');
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('encodes a traversal-style override id', async () => {
    await app.inject({
      method: 'POST',
      url: '/v1/hitl/overrides/..%2Fqueue/second-approval',
      headers,
      payload: { actor_id: 'b', ...ok },
    });
    const url = String(fetchSpy.mock.calls[0][0]);
    expect(url).toContain('/v1/hitl/overrides/..%2Fqueue/second-approval');
  });
});
