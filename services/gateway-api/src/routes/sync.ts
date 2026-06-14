import { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import { proxyToService } from '../proxy';

export const syncRoutes: FastifyPluginAsync = async (app): Promise<void> => {
  app.post('/sync/metadata', async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    await proxyToService(
      process.env.EGRESS_PROXY_URL || 'http://egress-proxy:8004',
      '/v1/sync/metadata',
      'POST',
      req.body,
      reply,
    );
  });
};
