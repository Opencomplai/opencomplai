import { describe, it, expect } from 'vitest';
import { buildApp } from '../index';

describe('GET /health', () => {
  it('returns 200 with status ok', async () => {
    process.env.OPENCOMPLAI_AUTH_DISABLED = '1';
    const app = buildApp();
    await app.ready();
    const response = await app.inject({
      method: 'GET',
      url: '/health',
    });
    await app.close();
    expect(response.statusCode).toBe(200);
    const body = JSON.parse(response.body);
    expect(body.status).toBe('ok');
    expect(body.service).toBe('gateway-api');
  });
});
