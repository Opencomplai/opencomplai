/**
 * Pro feature routes — badge issuance/verification and Pro ingest pipeline.
 *
 * All badge endpoints proxy to evidence-vault.
 * All ingest endpoints proxy to evidence-vault via egress-proxy (DLP enforced).
 */
import { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import { proxyToService } from '../proxy';

const EVIDENCE_VAULT_URL = process.env.EVIDENCE_VAULT_URL || 'http://evidence-vault:8002';
const EGRESS_PROXY_URL = process.env.EGRESS_PROXY_URL || 'http://egress-proxy:8004';

export const proRoutes: FastifyPluginAsync = async (app): Promise<void> => {
  // Badge issuance
  app.post('/pro/badges/issue', async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    await proxyToService(EVIDENCE_VAULT_URL, '/v1/pro/badges/issue', 'POST', req.body, reply);
  });

  // Badge verification
  app.get(
    '/pro/badges/verify/:badgeId',
    async (
      req: FastifyRequest<{ Params: { badgeId: string } }>,
      reply: FastifyReply,
    ): Promise<void> => {
      await proxyToService(
        EVIDENCE_VAULT_URL,
        `/v1/pro/badges/verify/${req.params.badgeId}`,
        'GET',
        undefined,
        reply,
      );
    },
  );

  // SVG badge asset
  app.get(
    '/pro/badges/:badgeId/svg',
    async (
      req: FastifyRequest<{ Params: { badgeId: string } }>,
      reply: FastifyReply,
    ): Promise<void> => {
      await proxyToService(
        EVIDENCE_VAULT_URL,
        `/v1/pro/badges/${req.params.badgeId}/svg`,
        'GET',
        undefined,
        reply,
      );
    },
  );

  // Pro ingest: status artifact (via egress-proxy DLP)
  app.post(
    '/pro/ingest/status-artifact',
    async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
      await proxyToService(
        EGRESS_PROXY_URL,
        '/v1/pro/ingest/status-artifact',
        'POST',
        req.body,
        reply,
      );
    },
  );

  // Pro ingest: dossier metadata (via egress-proxy DLP)
  app.post(
    '/pro/ingest/dossier-metadata',
    async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
      await proxyToService(
        EGRESS_PROXY_URL,
        '/v1/pro/ingest/dossier-metadata',
        'POST',
        req.body,
        reply,
      );
    },
  );

  // Pro ingest: metrics (via egress-proxy DLP)
  app.post(
    '/pro/ingest/metrics',
    async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
      await proxyToService(EGRESS_PROXY_URL, '/v1/pro/ingest/metrics', 'POST', req.body, reply);
    },
  );
};
