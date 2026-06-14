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
    async (_req: FastifyRequest, reply: FastifyReply): Promise<void> => {
      await proxyToService(
        process.env.EVIDENCE_VAULT_URL || 'http://evidence-vault:8002',
        '/v1/evidence/ledger-history-tips',
        'GET',
        undefined,
        reply,
      );
    },
  );
};
