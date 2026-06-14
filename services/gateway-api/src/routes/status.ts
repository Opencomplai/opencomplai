import { FastifyPluginAsync } from 'fastify';

export const statusRoutes: FastifyPluginAsync = async (app): Promise<void> => {
  app.get('/status', async () => ({
    status: 'ok',
    version: '0.1.0-dev',
    services: {},
  }));
};
