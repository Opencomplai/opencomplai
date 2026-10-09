import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { FastifyReply } from 'fastify';
import { proxyToService } from '../proxy';
import { _resetSharedSecretCacheForTests } from '../serviceAuth';

function fakeReply(tenantId?: string): FastifyReply {
  return {
    status: vi.fn().mockReturnThis(),
    send: vi.fn().mockReturnThis(),
    request: {
      tenantId,
      id: 'req-1',
      log: { error: vi.fn() },
      raw: { on: vi.fn(), off: vi.fn() },
    },
  } as unknown as FastifyReply;
}

describe('proxyToService service-token attachment (SEC-SERVICE-AUTH)', () => {
  const original = process.env.INTERNAL_SERVICE_TOKEN_SECRET;
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn(async () => new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    if (original === undefined) {
      delete process.env.INTERNAL_SERVICE_TOKEN_SECRET;
    } else {
      process.env.INTERNAL_SERVICE_TOKEN_SECRET = original;
    }
    _resetSharedSecretCacheForTests();
  });

  it('attaches a Bearer token when the shared secret is configured', async () => {
    process.env.INTERNAL_SERVICE_TOKEN_SECRET = 'shared-secret';
    _resetSharedSecretCacheForTests();

    await proxyToService('http://risk-engine:8001', '/v1/risk/classify', 'POST', {}, fakeReply());

    const sentHeaders = fetchSpy.mock.calls[0][1]?.headers as Record<string, string>;
    expect(sentHeaders.Authorization).toMatch(/^Bearer .+\..+$/);
  });

  it('omits the Authorization header when no shared secret is configured', async () => {
    delete process.env.INTERNAL_SERVICE_TOKEN_SECRET;
    _resetSharedSecretCacheForTests();

    await proxyToService('http://risk-engine:8001', '/v1/risk/classify', 'POST', {}, fakeReply());

    const sentHeaders = fetchSpy.mock.calls[0][1]?.headers as Record<string, string>;
    expect(sentHeaders.Authorization).toBeUndefined();
  });
});

describe('proxyToService tenant header forwarding (TEN-VAULT)', () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn(async () => new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('forwards X-Tenant-Id when the request carries a resolved tenant', async () => {
    await proxyToService(
      'http://evidence-vault:8002',
      '/v1/evidence/events',
      'POST',
      {},
      fakeReply('tenant-a'),
    );

    const sentHeaders = fetchSpy.mock.calls[0][1]?.headers as Record<string, string>;
    expect(sentHeaders['X-Tenant-Id']).toBe('tenant-a');
  });

  it('omits X-Tenant-Id when the request has no resolved tenant (auth disabled)', async () => {
    await proxyToService(
      'http://evidence-vault:8002',
      '/v1/evidence/events',
      'POST',
      {},
      fakeReply(),
    );

    const sentHeaders = fetchSpy.mock.calls[0][1]?.headers as Record<string, string>;
    expect(sentHeaders['X-Tenant-Id']).toBeUndefined();
  });
});
