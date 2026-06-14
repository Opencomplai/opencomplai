import { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import { z } from 'zod';
import { proxyToService } from '../proxy';

const OverrideSchema = z.object({
  case_id: z.string().min(1),
  actor_id: z.string().min(1),
  rationale: z.string().min(1),
  decision: z.enum(['approved', 'rejected']),
  idempotency_key: z.string().optional(),
});

const DecideSchema = z.object({
  actor_id: z.string().min(1),
  rationale: z.string().min(1),
  decision: z.enum(['approved', 'rejected']),
  idempotency_key: z.string().optional(),
});

const AssignSchema = z.object({
  reviewer_id: z.string().min(1),
});

const RISK_ENGINE = process.env.RISK_ENGINE_URL || 'http://risk-engine:8001';

export const hitlRoutes: FastifyPluginAsync = async (app): Promise<void> => {
  app.get('/hitl/queue', async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    const q = req.query as { state?: string; assigned_to?: string };
    const params = new URLSearchParams();
    if (q.state) params.set('state', q.state);
    if (q.assigned_to) params.set('assigned_to', q.assigned_to);
    const qs = params.toString();
    await proxyToService(
      RISK_ENGINE,
      `/v1/hitl/queue${qs ? `?${qs}` : ''}`,
      'GET',
      undefined,
      reply,
    );
  });

  app.get('/hitl/queue/:id', async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    const { id } = req.params as { id: string };
    await proxyToService(RISK_ENGINE, `/v1/hitl/queue/${id}`, 'GET', undefined, reply);
  });

  app.post(
    '/hitl/queue/:id/assign',
    async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
      const { id } = req.params as { id: string };
      const parsed = AssignSchema.safeParse(req.body);
      if (!parsed.success) {
        reply.status(422).send({
          error_code: 'VALIDATION_ERROR',
          message: parsed.error.message,
          category: 'client',
          retryable: false,
          correlation_id: req.id,
        });
        return;
      }
      await proxyToService(RISK_ENGINE, `/v1/hitl/queue/${id}/assign`, 'POST', parsed.data, reply);
    },
  );

  app.post(
    '/hitl/queue/:id/decide',
    async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
      const { id } = req.params as { id: string };
      const parsed = DecideSchema.safeParse(req.body);
      if (!parsed.success) {
        reply.status(422).send({
          error_code: 'VALIDATION_ERROR',
          message: parsed.error.message,
          category: 'client',
          retryable: false,
          correlation_id: req.id,
        });
        return;
      }
      await proxyToService(RISK_ENGINE, `/v1/hitl/queue/${id}/decide`, 'POST', parsed.data, reply);
    },
  );

  app.post('/hitl/overrides', async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
    const parsed = OverrideSchema.safeParse(req.body);
    if (!parsed.success) {
      reply.status(422).send({
        error_code: 'VALIDATION_ERROR',
        message: parsed.error.message,
        category: 'client',
        retryable: false,
        correlation_id: req.id,
      });
      return;
    }

    await proxyToService(RISK_ENGINE, '/v1/hitl/overrides', 'POST', parsed.data, reply);
  });
};
