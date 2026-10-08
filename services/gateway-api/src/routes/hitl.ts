import { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import { z } from 'zod';
import { proxyToService } from '../proxy';

const OverrideSchema = z.object({
  case_id: z.string().min(1),
  actor_id: z.string().min(1),
  rationale: z.string().min(1),
  decision: z.enum(['approved', 'rejected']),
  requires_dual_approval: z.boolean().optional(),
  idempotency_key: z.string().optional(),
});

const SecondApprovalSchema = z.object({
  actor_id: z.string().min(1),
  rationale: z.string().min(1),
  rationale_hash: z.string().min(1),
  decision: z.enum(['approved', 'rejected']).default('approved'),
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

/**
 * Bind actor_id/reviewer_id to the gateway-verified principal (SEC-SERVICE-AUTH)
 * rather than trusting the client-supplied body field — otherwise any
 * network-adjacent caller could forge whose decision lands in the immutable
 * ledger. request.principalId is unset only under OPENCOMPLAI_AUTH_DISABLED=1
 * (local dev), where falling back to the client-supplied value preserves the
 * existing bypass rather than breaking local development.
 */
function resolveActorId(request: FastifyRequest, clientSupplied: string): string {
  return request.principalId ?? clientSupplied;
}

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
    await proxyToService(
      RISK_ENGINE,
      `/v1/hitl/queue/${encodeURIComponent(id)}`,
      'GET',
      undefined,
      reply,
    );
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
      await proxyToService(
        RISK_ENGINE,
        `/v1/hitl/queue/${encodeURIComponent(id)}/assign`,
        'POST',
        { ...parsed.data, reviewer_id: resolveActorId(req, parsed.data.reviewer_id) },
        reply,
      );
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
      await proxyToService(
        RISK_ENGINE,
        `/v1/hitl/queue/${encodeURIComponent(id)}/decide`,
        'POST',
        { ...parsed.data, actor_id: resolveActorId(req, parsed.data.actor_id) },
        reply,
      );
    },
  );

  app.post(
    '/hitl/overrides/:override_id/second-approval',
    async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
      const { override_id } = req.params as { override_id: string };
      const parsed = SecondApprovalSchema.safeParse(req.body);
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
      await proxyToService(
        RISK_ENGINE,
        `/v1/hitl/overrides/${encodeURIComponent(override_id)}/second-approval`,
        'POST',
        { ...parsed.data, actor_id: resolveActorId(req, parsed.data.actor_id) },
        reply,
      );
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

    await proxyToService(
      RISK_ENGINE,
      '/v1/hitl/overrides',
      'POST',
      { ...parsed.data, actor_id: resolveActorId(req, parsed.data.actor_id) },
      reply,
    );
  });
};
