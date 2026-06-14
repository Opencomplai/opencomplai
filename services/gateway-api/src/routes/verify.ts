import { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import { proxyToService } from '../proxy';

export const verifyRoutes: FastifyPluginAsync = async (app): Promise<void> => {
  app.post('/verify/claims', async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    await proxyToService(
      process.env.RISK_ENGINE_URL || 'http://risk-engine:8001',
      '/v1/verify/claims',
      'POST',
      req.body,
      reply,
    );
  });
};
