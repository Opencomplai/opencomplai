import { FastifyPluginAsync } from 'fastify';
import { aggregateDownstreamHealth } from '../downstreamHealth';

/**
 * GET /v1/status — system status, aggregated across every downstream service.
 *
 * Previously returned a hardcoded `services: {}` without contacting anything,
 * which made it useless for orchestration or a status page (OPS-HEALTH,
 * finding 40).
 *
 * **Status code semantics.** The default is 200 even when a downstream is
 * degraded: the request succeeded and the body is a complete, accurate answer.
 * Many monitors and HTTP clients treat a non-2xx as "fetch failed" and never
 * parse the body, so defaulting to 503 would discard the per-service detail in
 * exactly the situation this endpoint exists for — and a bare 503 cannot
 * distinguish "gateway is down" from "one downstream is flaky".
 *
 * For code-only monitors, `?strict=1` returns **503 when anything is not ok**
 * (including a probe that timed out — "could not look" is degraded, never ok).
 * `?strict=1` is the canonical monitoring target; see
 * `docs/src/deployment/monitoring.md`. The default's failure mode is silent
 * green, so a monitor configured without it shows healthy while degraded.
 *
 * This is NOT a liveness probe. `GET /health` is the gateway's own liveness and
 * contacts nothing — never point a liveness or readiness probe at `/v1/status`,
 * or a single dead downstream will restart a perfectly healthy gateway.
 */
export const statusRoutes: FastifyPluginAsync = async (app): Promise<void> => {
  app.get<{ Querystring: { strict?: string } }>('/status', async (request, reply) => {
    const aggregate = await aggregateDownstreamHealth();

    const body = {
      status: aggregate.status,
      service: 'gateway-api',
      version: '0.9.1',
      checked_at: new Date().toISOString(),
      services: aggregate.services,
    };

    const strict = request.query?.strict === '1' || request.query?.strict === 'true';
    return reply.status(strict && aggregate.status !== 'ok' ? 503 : 200).send(body);
  });
};
