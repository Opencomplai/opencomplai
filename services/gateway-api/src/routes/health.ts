import { FastifyPluginAsync } from 'fastify';

export const healthRoutes: FastifyPluginAsync = async (app): Promise<void> => {
  app.get('/health', async () => ({
    status: 'ok',
    service: 'gateway-api',
    version: '0.9.0',
  }));
};
