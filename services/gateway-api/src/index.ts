import Fastify, { FastifyInstance } from 'fastify';
import { authMiddleware } from './middleware/auth';
import { registerRoutes } from './routes';

/**
 * Build a Fastify app instance.
 *
 * Throws synchronously if the auth middleware cannot be configured safely
 * (e.g. no API key set in production). Callers (server.ts) must let the
 * exception propagate so the process exits with a non-zero code rather than
 * silently coming up unauthenticated.
 */
export function buildApp(): FastifyInstance {
  const app = Fastify({
    logger: process.env.NODE_ENV !== 'test',
  });

  // Run synchronously; any configuration error bubbles up so server.ts
  // can fail the process start rather than booting in an unsafe state.
  authMiddleware(app);
  void registerRoutes(app);

  return app;
}
