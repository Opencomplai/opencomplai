import { FastifyReply } from 'fastify';
import { loadSharedSecret, mintServiceToken } from './serviceAuth';

const DEFAULT_PROXY_TIMEOUT_MS = 30_000;
// setTimeout wraps a larger delay around to 1 ms.
const MAX_TIMER_MS = 2_147_483_647;

/** Upstream timeout from PROXY_TIMEOUT_MS; anything but a positive number falls back to 30 s. */
function proxyTimeoutMs(): number {
  const n = Number(process.env.PROXY_TIMEOUT_MS);
  return Number.isFinite(n) && n > 0 ? Math.min(n, MAX_TIMER_MS) : DEFAULT_PROXY_TIMEOUT_MS;
}

/**
 * The four internal Python services (risk-engine, evidence-vault,
 * doc-generator, egress-proxy) require a signed service token on every
 * non-health route (SEC-SERVICE-AUTH). gateway-api is their sole authenticated
 * caller, so it mints one per outbound call here — the single choke point
 * every route module proxies through.
 */
function serviceAuthHeaders(): Record<string, string> {
  const secret = loadSharedSecret();
  if (!secret) return {};
  const token = mintServiceToken('gateway-api', secret);
  return { Authorization: `Bearer ${token}` };
}

export async function proxyToService(
  serviceBaseUrl: string,
  path: string,
  method: string,
  body: unknown,
  reply: FastifyReply,
): Promise<void> {
  const url = `${serviceBaseUrl}${path}`;
  // Forward the gateway-verified caller's tenant (TEN-VAULT) so evidence-vault's
  // RLS fence has something to scope to. Absent only when
  // OPENCOMPLAI_AUTH_DISABLED=1 (local dev), in which case evidence-vault falls
  // back to its own OSS_DEFAULT_TENANT_ID.
  const tenantId = reply.request?.tenantId;
  const tenantHeaders: Record<string, string> = tenantId ? { 'X-Tenant-Id': tenantId } : {};

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), proxyTimeoutMs());

  // Abort the upstream call when the client goes away before the reply is out.
  // Listen on the reply's socket-side stream: the REQUEST stream emits 'close'
  // as soon as its body has been read (Node 16+), which would abort every
  // proxied call that has a body.
  const onClientClose = (): void => {
    if (!reply.raw.writableFinished) controller.abort();
  };
  reply.raw?.on('close', onClientClose);

  try {
    const response = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...serviceAuthHeaders(),
        ...tenantHeaders,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    const raw = await response.text();
    let data: unknown = undefined;
    if (raw.length > 0) {
      try {
        data = JSON.parse(raw);
      } catch {
        data = { raw };
      }
    }

    reply.status(response.status).send(data);
  } catch (err: unknown) {
    const isAbort = err instanceof Error && err.name === 'AbortError';
    // The upstream URL is logged here and never sent to the client.
    reply.request?.log?.error(
      { err, upstream_url: url },
      isAbort ? 'Upstream proxy aborted (timeout or client disconnect)' : 'Upstream proxy failed',
    );

    reply.status(503).send({
      error_code: 'DEPENDENCY_UNAVAILABLE',
      message: 'Upstream service unavailable.',
      category: 'dependency',
      retryable: true,
      correlation_id: reply.request?.id,
    });
  } finally {
    clearTimeout(timeoutId);
    reply.raw?.off('close', onClientClose);
  }
}
