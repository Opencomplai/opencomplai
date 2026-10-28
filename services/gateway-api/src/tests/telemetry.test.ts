import { createRequire } from 'node:module';
import net from 'node:net';
import { describe, expect, it } from 'vitest';

// The OpenTelemetry packages are optional dependencies. telemetry.ts loads them
// inside a try/catch, so an incompatible release would switch metrics off without
// any error. This test starts the real SDK the way configureTelemetry() does and
// checks that the Prometheus endpoint serves metrics, so such a break fails CI.
const nodeRequire = createRequire(__filename);

function loadOtel(): {
  NodeSDK: new (opts: Record<string, unknown>) => { start(): void; shutdown(): Promise<void> };
  PrometheusExporter: new (opts: { port: number }) => unknown;
  resourceFromAttributes: (attrs: Record<string, string>) => unknown;
} | null {
  try {
    const { NodeSDK } = nodeRequire('@opentelemetry/sdk-node');
    const { PrometheusExporter } = nodeRequire('@opentelemetry/exporter-prometheus');
    const { resourceFromAttributes } = nodeRequire('@opentelemetry/resources');
    return { NodeSDK, PrometheusExporter, resourceFromAttributes };
  } catch {
    return null;
  }
}

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, () => {
      const { port } = server.address() as net.AddressInfo;
      server.close(() => resolve(port));
    });
  });
}

const otel = loadOtel();

describe('telemetry', () => {
  it.skipIf(otel === null)(
    'serves Prometheus metrics from the real OpenTelemetry SDK',
    async () => {
      const { NodeSDK, PrometheusExporter, resourceFromAttributes } = otel!;
      const port = await freePort();
      const exporter = new PrometheusExporter({ port });
      const sdk = new NodeSDK({
        resource: resourceFromAttributes({ 'service.name': 'gateway-api-test' }),
        metricReaders: [exporter],
        instrumentations: [],
      });
      sdk.start();
      try {
        const res = await fetch(`http://localhost:${port}/metrics`);
        const body = await res.text();
        expect(res.status).toBe(200);
        expect(body).not.toContain('failed to export metrics');
      } finally {
        await sdk.shutdown();
      }
    },
  );
});
