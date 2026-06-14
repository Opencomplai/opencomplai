import { FastifyPluginAsync, FastifyReply, FastifyRequest } from 'fastify';
import { z } from 'zod';
import { proxyToService } from '../proxy';

const SystemManifestSchema = z
  .object({
    system_id: z.string().min(1),
    intended_purpose: z.string().min(1),
    compliance_target: z.string().default('EU_AI_ACT'),
    high_risk_presumption: z.boolean().default(false),
    commit_ref: z.string().default('HEAD'),
    // Optional Annex IV Section 2 / 3 inputs. Stripped to typed values so
    // upstream services receive a well-formed manifest, but absent fields
    // remain absent rather than turning into nulls in the proxied payload.
    training_data_description: z.string().nullable().optional(),
    model_architecture: z.string().nullable().optional(),
    performance_metrics: z.record(z.string(), z.number()).optional(),
    known_limitations: z.array(z.string()).optional(),
    human_oversight_measures: z.array(z.string()).optional(),
    monitoring_approach: z.string().nullable().optional(),
    incident_response_procedure: z.string().nullable().optional(),
  })
  .passthrough();

export const manifestRoutes: FastifyPluginAsync = async (app): Promise<void> => {
  app.post(
    '/manifests/validate',
    async (req: FastifyRequest, reply: FastifyReply): Promise<void> => {
      const parsed = SystemManifestSchema.safeParse(req.body);
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
        process.env.RISK_ENGINE_URL || 'http://risk-engine:8001',
        '/v1/manifests/validate',
        'POST',
        parsed.data,
        reply,
      );
    },
  );
};
