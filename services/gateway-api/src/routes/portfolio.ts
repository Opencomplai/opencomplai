/**
 * Portfolio route — lists the AI systems on record with their latest
 * compliance badge. Proxies to evidence-vault, which owns the data.
 */
import { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import { proxyToService } from '../proxy';

const EVIDENCE_VAULT_URL = process.env.EVIDENCE_VAULT_URL || 'http://evidence-vault:8002';

export const portfolioRoutes: FastifyPluginAsync = async (app): Promise<void> => {
  app.get('/portfolio', async (_req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    await proxyToService(EVIDENCE_VAULT_URL, '/v1/portfolio', 'GET', undefined, reply);
  });
};
