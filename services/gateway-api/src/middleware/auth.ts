import { FastifyInstance, FastifyReply, FastifyRequest } from 'fastify';
import type { webcrypto } from 'node:crypto';

/**
 * Auth middleware (ISO 27001 A.8.5 / SOC 2 CC6.1 / NIST PR.AA / FedRAMP IA-2).
 *
 * Two modes — see docs/deployment/authentication.md for when to use each:
 *
 * 1. OIDC JWT mode (multi-user / SaaS): set OIDC_JWKS_URI.
 *    Every non-health request must carry a valid Bearer JWT.
 *
 * 2. API-key mode (self-hosted / single-operator): set OPENCOMPLAI_API_KEY.
 *    Every non-health request must carry x-api-key header.
 *    Fallback when OIDC_JWKS_URI is not set.
 */
export function authMiddleware(app: FastifyInstance): void {
  const apiKey = process.env.OPENCOMPLAI_API_KEY;
  const authDisabled = process.env.OPENCOMPLAI_AUTH_DISABLED === '1';
  const oidcJwksUri = process.env.OIDC_JWKS_URI;

  if (oidcJwksUri) {
    app.log.info(`Gateway using OIDC JWT auth (JWKS: ${oidcJwksUri})`);
    app.addHook(
      'onRequest',
      async (request: FastifyRequest, reply: FastifyReply): Promise<void> => {
        if (request.url === '/health' || request.url.startsWith('/health?')) return;
        const authHeader = request.headers['authorization'];
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
          reply.status(401).send({
            error_code: 'POLICY_DENIED',
            message: 'Missing Bearer token.',
            category: 'policy',
            retryable: false,
            correlation_id: request.id,
          });
          return;
        }
        const valid = await _verifyJwt(authHeader.slice(7), oidcJwksUri, app);
        if (!valid) {
          reply.status(401).send({
            error_code: 'POLICY_DENIED',
            message: 'Invalid or expired JWT.',
            category: 'policy',
            retryable: false,
            correlation_id: request.id,
          });
        }
      },
    );
    return;
  }

  if (!apiKey) {
    if (!authDisabled) {
      const msg =
        'Gateway refusing to start: OPENCOMPLAI_API_KEY is not set. ' +
        'Set it to a strong shared secret, or explicitly opt out with ' +
        'OPENCOMPLAI_AUTH_DISABLED=1 for local development.';
      app.log.error(msg);
      throw new Error(msg);
    }
    app.log.warn(
      'Gateway running WITHOUT authentication (OPENCOMPLAI_AUTH_DISABLED=1). Do not use in production.',
    );
    return;
  }

  app.addHook('onRequest', async (request: FastifyRequest, reply: FastifyReply): Promise<void> => {
    if (request.url === '/health' || request.url.startsWith('/health?')) return;
    const provided = request.headers['x-api-key'];
    const providedKey = Array.isArray(provided) ? provided[0] : provided;
    if (providedKey !== apiKey) {
      reply.status(401).send({
        error_code: 'POLICY_DENIED',
        message: 'Invalid or missing API key.',
        category: 'policy',
        retryable: false,
        correlation_id: request.id,
      });
    }
  });
}

/** Minimal JWKS JWT verifier using Node.js crypto. For production use jose or jwks-rsa. */
async function _verifyJwt(token: string, jwksUri: string, app: FastifyInstance): Promise<boolean> {
  try {
    const [headerB64, payloadB64, sigB64] = token.split('.');
    const header = JSON.parse(Buffer.from(headerB64, 'base64url').toString()) as {
      kid?: string;
      alg?: string;
    };
    const resp = await fetch(jwksUri);
    if (!resp.ok) {
      app.log.warn(`JWKS fetch failed: ${resp.status}`);
      return false;
    }
    const jwks = (await resp.json()) as { keys: Array<{ kid?: string; [k: string]: unknown }> };
    const key = jwks.keys.find((k) => k.kid === header.kid);
    if (!key) {
      app.log.warn(`No matching key for kid=${header.kid}`);
      return false;
    }
    const { createPublicKey, createVerify } = await import('node:crypto');
    const pubKey = createPublicKey({ key: key as webcrypto.JsonWebKey, format: 'jwk' });
    const alg = header.alg ?? 'RS256';
    const nodeAlg = alg.startsWith('RS') ? 'RSA-SHA256' : 'SHA256';
    const verifier = createVerify(nodeAlg);
    verifier.update(`${headerB64}.${payloadB64}`);
    return verifier.verify(pubKey, Buffer.from(sigB64, 'base64url'));
  } catch (err) {
    app.log.warn(`JWT verification error: ${err}`);
    return false;
  }
}
