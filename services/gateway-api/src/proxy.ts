import { FastifyReply } from 'fastify';

export async function proxyToService(
  serviceBaseUrl: string,
  path: string,
  method: string,
  body: unknown,
  reply: FastifyReply,
): Promise<void> {
  const url = `${serviceBaseUrl}${path}`;
  try {
    const response = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    const raw = await response.text();
    let data: unknown = undefined;
    if (raw.length > 0) {
      try {
        data = JSON.parse(raw);
      } catch {
        data = { raw };
      }
    }

    reply.status(response.status).send(data);
  } catch {
    reply.status(503).send({
      error_code: 'DEPENDENCY_UNAVAILABLE',
      message: `Upstream service unavailable: ${url}`,
      category: 'dependency',
      retryable: true,
      correlation_id: reply.request.id,
    });
  }
}
