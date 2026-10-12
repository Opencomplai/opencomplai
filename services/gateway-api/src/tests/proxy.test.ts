import { createServer, type Server } from 'node:http';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Fastify, { FastifyReply } from 'fastify';
import { proxyToService } from '../proxy';
import { _resetSharedSecretCacheForTests } from '../serviceAuth';

function fakeReply(tenantId?: string): FastifyReply {
  return {
    status: vi.fn().mockReturnThis(),
    send: vi.fn().mockReturnThis(),
    raw: { on: vi.fn(), off: vi.fn(), writableFinished: false },
    request: {
      tenantId,
      id: 'req-1',
      log: { error: vi.fn() },
    },
  } as unknown as FastifyReply;
}

/** A reply that records the 'close' listener proxyToService registers on the response stream. */
function closableReply(): { reply: FastifyReply; close: (finished: boolean) => void } {
  let listener: (() => void) | undefined;
  const raw = {
    on: vi.fn((event: string, fn: () => void): void => {
      if (event === 'close') listener = fn;
    }),
    off: vi.fn(),
    writableFinished: false,
  };
  const reply = {
    status: vi.fn().mockReturnThis(),
    send: vi.fn().mockReturnThis(),
    raw,
    request: { id: 'req-1', log: { error: vi.fn() } },
  } as unknown as FastifyReply;
  return {
    reply,
    close: (finished: boolean): void => {
      raw.writableFinished = finished;
      listener?.();
    },
  };
}

/** fetch stand-in that never answers and rejects with AbortError when its signal fires. */
function hangingFetch(): ReturnType<typeof vi.fn> {
  return vi.fn(
    (_url: string, init?: { signal?: AbortSignal }) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          const e = new Error('The operation was aborted');
          e.name = 'AbortError';
          reject(e);
        });
      }),
  );
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

describe('proxyToService upstream failure handling', () => {
  const originalTimeout = process.env.PROXY_TIMEOUT_MS;

  afterEach(() => {
    vi.unstubAllGlobals();
    if (originalTimeout === undefined) delete process.env.PROXY_TIMEOUT_MS;
    else process.env.PROXY_TIMEOUT_MS = originalTimeout;
  });

  it('never puts the upstream address in the 503 body, and logs it server-side', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new Error('connect ECONNREFUSED risk-engine:8001');
      }),
    );
    const reply = fakeReply();

    await proxyToService('http://risk-engine:8001', '/v1/risk/classify', 'POST', {}, reply);

    expect(reply.status).toHaveBeenCalledWith(503);
    const body = (reply.send as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(body.error_code).toBe('DEPENDENCY_UNAVAILABLE');
    expect(body.message).toBe('Upstream service unavailable.');
    expect(JSON.stringify(body)).not.toContain('risk-engine');
    expect(body.correlation_id).toBe('req-1');
    const logged = (reply.request.log.error as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(logged.upstream_url).toBe('http://risk-engine:8001/v1/risk/classify');
  });

  it('answers 503 when the upstream does not reply within PROXY_TIMEOUT_MS', async () => {
    process.env.PROXY_TIMEOUT_MS = '25';
    vi.stubGlobal('fetch', hangingFetch());
    const reply = fakeReply();

    await proxyToService('http://doc-generator:8003', '/v1/docs', 'POST', {}, reply);

    expect(reply.status).toHaveBeenCalledWith(503);
    const body = (reply.send as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(body.error_code).toBe('DEPENDENCY_UNAVAILABLE');
    expect(body.retryable).toBe(true);
  });

  it('uses a 30 s timeout when PROXY_TIMEOUT_MS is not a positive number', async () => {
    const spy = vi.spyOn(globalThis, 'setTimeout');
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('{}', { status: 200 })),
    );
    for (const bad of ['', 'abc', '0', '-5']) {
      process.env.PROXY_TIMEOUT_MS = bad;
      spy.mockClear();
      await proxyToService('http://risk-engine:8001', '/x', 'GET', undefined, fakeReply());
      expect(spy.mock.calls[0][1]).toBe(30_000);
    }
    spy.mockRestore();
  });

  it('aborts the upstream call when the client drops before the reply is sent', async () => {
    vi.stubGlobal('fetch', hangingFetch());
    const { reply, close } = closableReply();

    const pending = proxyToService('http://evidence-vault:8002', '/v1/e', 'POST', {}, reply);
    close(false);
    await pending;

    expect(reply.status).toHaveBeenCalledWith(503);
  });

  it('does not abort on a response stream that has already finished', async () => {
    let release: (r: Response) => void = () => undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise<Response>((resolve) => (release = resolve))),
    );
    const { reply, close } = closableReply();

    const pending = proxyToService('http://evidence-vault:8002', '/v1/e', 'POST', {}, reply);
    close(true);
    release(new Response('{"ok":true}', { status: 200 }));
    await pending;

    expect(reply.status).toHaveBeenCalledWith(200);
  });

  it('removes its close listener once the call has finished', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('{}', { status: 200 })),
    );
    const reply = fakeReply();

    await proxyToService('http://risk-engine:8001', '/x', 'GET', undefined, reply);

    expect(reply.raw.off).toHaveBeenCalledWith('close', expect.any(Function));
  });
});

describe('proxyToService over a real socket', () => {
  let upstream: Server;

  beforeEach(async () => {
    upstream = createServer((req, res) => {
      req.resume();
      setTimeout(() => {
        res.setHeader('content-type', 'application/json');
        res.end('{"ok":true}');
      }, 100);
    });
    await new Promise<void>((resolve) => upstream.listen(0, '127.0.0.1', resolve));
  });

  afterEach(async () => {
    await new Promise<void>((resolve) => upstream.close(() => resolve()));
  });

  // The request stream emits 'close' once its body has been read, so a listener on
  // it would abort every proxied call that carries a body.
  it('completes a proxied POST that carries a body', async () => {
    const port = (upstream.address() as { port: number }).port;
    const app = Fastify();
    app.post('/p', async (request, reply) => {
      await proxyToService(`http://127.0.0.1:${port}`, '/v1/x', 'POST', request.body, reply);
    });

    await app.listen({ port: 0, host: '127.0.0.1' });
    try {
      const appPort = (app.server.address() as { port: number }).port;
      const res = await fetch(`http://127.0.0.1:${appPort}/p`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: '{"a":1}',
      });
      expect(res.status).toBe(200);
      expect(await res.json()).toEqual({ ok: true });
    } finally {
      await app.close();
    }
  });
});
