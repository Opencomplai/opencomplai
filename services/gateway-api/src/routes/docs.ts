import { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import { proxyToService } from '../proxy';

const docGeneratorUrl = (): string => process.env.DOC_GENERATOR_URL || 'http://doc-generator:8003';

export const docsRoutes: FastifyPluginAsync = async (app): Promise<void> => {
  app.post('/docs/generate', async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    await proxyToService(docGeneratorUrl(), '/v1/docs/generate', 'POST', req.body, reply);
  });

  app.get<{ Querystring: { system_id?: string } }>(
    '/docs',
    async (req, reply: FastifyReply): Promise<void> => {
      const systemId = req.query.system_id;
      if (!systemId) {
        reply.status(422).send({
          error_code: 'VALIDATION_ERROR',
          message: 'Query parameter "system_id" is required.',
          category: 'validation',
          retryable: false,
          correlation_id: req.id,
        });
        return;
      }
      const upstreamPath = `/v1/docs?system_id=${encodeURIComponent(systemId)}`;
      await proxyToService(docGeneratorUrl(), upstreamPath, 'GET', undefined, reply);
    },
  );

  app.get<{ Params: { dossier_id: string } }>(
    '/docs/:dossier_id',
    async (req, reply: FastifyReply): Promise<void> => {
      const dossierId = encodeURIComponent(req.params.dossier_id);
      await proxyToService(docGeneratorUrl(), `/v1/docs/${dossierId}`, 'GET', undefined, reply);
    },
  );
};
