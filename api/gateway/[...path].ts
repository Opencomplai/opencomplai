/**
 * Vercel serverless entry point for the gateway-api service.
 *
 * Fastify doesn't expose a raw http.Handler, so we wrap it with a small
 * adapter: inject the incoming VercelRequest into Fastify's inject() method
 * and pipe the response back. This keeps all routing/auth logic in the
 * existing buildApp() function with zero changes.
 */
import type { VercelRequest, VercelResponse } from "@vercel/node";
import { buildApp } from "../../services/gateway-api/src/index";

// Build once per cold start (Fastify instance is reused across warm invocations).
const app = buildApp();
// Fastify must be ready before inject() can be called.
const ready = app.ready();

export default async function handler(
  req: VercelRequest,
  res: VercelResponse,
): Promise<void> {
  await ready;

  const url = req.url ?? "/";
  const method = req.method ?? "GET";

  // Collect raw body bytes if present.
  const bodyChunks: Buffer[] = [];
  for await (const chunk of req) {
    bodyChunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  const payload = bodyChunks.length > 0 ? Buffer.concat(bodyChunks) : undefined;

  const response = await app.inject({
    method: method as Parameters<typeof app.inject>[0]["method"],
    url,
    headers: req.headers as Record<string, string>,
    payload,
  });

  res.status(response.statusCode);
  for (const [key, value] of Object.entries(response.headers)) {
    if (value !== undefined) res.setHeader(key, value as string);
  }
  res.send(response.rawPayload);
}
