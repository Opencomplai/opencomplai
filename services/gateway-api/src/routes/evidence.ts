import { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import { proxyToService } from '../proxy';

export const evidenceRoutes: FastifyPluginAsync = async (app): Promise<void> => {
  app.post('/evidence/events', async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    await proxyToService(
      process.env.EVIDENCE_VAULT_URL || 'http://evidence-vault:8002',
      '/v1/evidence/events',
      'POST',
      req.body,
      reply,
    );
  });

  app.get(
    '/evidence/verify-chain',
    async (_req: FastifyRequest, reply: FastifyReply): Promise<void> => {
      await proxyToService(
        process.env.EVIDENCE_VAULT_URL || 'http://evidence-vault:8002',
        '/v1/evidence/verify-chain',
        'GET',
        undefined,
        reply,
      );
    },
  );

  app.get(
    '/evidence/ledger-root',
    async (_req: FastifyRequest, reply: FastifyReply): Promise<void> => {
      await proxyToService(
        process.env.EVIDENCE_VAULT_URL || 'http://evidence-vault:8002',
        '/v1/evidence/ledger-root',
        'GET',
        undefined,
        reply,
      );
    },
  );

  app.get(
    '/evidence/ledger-history-tips',
    async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
      // Forward only the paging parameters; the vault owns their validation.
      const q = req.query as { after_seq?: string; limit?: string };
      const params = new URLSearchParams();
      if (q.after_seq) params.set('after_seq', q.after_seq);
      if (q.limit) params.set('limit', q.limit);
      const qs = params.toString();
      await proxyToService(
        process.env.EVIDENCE_VAULT_URL || 'http://evidence-vault:8002',
        `/v1/evidence/ledger-history-tips${qs ? `?${qs}` : ''}`,
        'GET',
        undefined,
        reply,
      );
    },
  );
};
