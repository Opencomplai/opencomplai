import { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import { proxyToService } from '../proxy';

export const riskRoutes: FastifyPluginAsync = async (app): Promise<void> => {
  app.post('/risk/classify', async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    await proxyToService(
      process.env.RISK_ENGINE_URL || 'http://risk-engine:8001',
      '/v1/risk/classify',
      'POST',
      req.body,
      reply,
    );
  });
};
