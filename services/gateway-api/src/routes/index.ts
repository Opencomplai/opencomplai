import { FastifyInstance } from 'fastify';
import { docsRoutes } from './docs';
import { evidenceRoutes } from './evidence';
import { healthRoutes } from './health';
import { hitlRoutes } from './hitl';
import { manifestRoutes } from './manifests';
import { portfolioRoutes } from './portfolio';
import { proRoutes } from './pro';
import { riskRoutes } from './risk';
import { statusRoutes } from './status';
import { syncRoutes } from './sync';
import { verifyRoutes } from './verify';

export async function registerRoutes(app: FastifyInstance): Promise<void> {
  await app.register(healthRoutes);
  await app.register(manifestRoutes, { prefix: '/v1' });
  await app.register(riskRoutes, { prefix: '/v1' });
  await app.register(evidenceRoutes, { prefix: '/v1' });
  await app.register(verifyRoutes, { prefix: '/v1' });
  await app.register(hitlRoutes, { prefix: '/v1' });
  await app.register(docsRoutes, { prefix: '/v1' });
  await app.register(syncRoutes, { prefix: '/v1' });
  await app.register(statusRoutes, { prefix: '/v1' });
  await app.register(proRoutes, { prefix: '/v1' });
  await app.register(portfolioRoutes, { prefix: '/v1' });
}
