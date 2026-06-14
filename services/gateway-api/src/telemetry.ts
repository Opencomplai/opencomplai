// OpenTelemetry instrumentation for the gateway-api service.
//
// Loaded by server.ts before any business code so that the NodeSDK can patch
// http/fetch/Fastify spans correctly. Telemetry is opt-in: if the optional
// @opentelemetry/* dependencies are not installed (e.g. local dev / tests),
// configureTelemetry() is a silent no-op.
//
// Prometheus metrics are exposed on a separate port (default 9464) so the
// scrape surface stays distinct from the public Fastify routes.

const SERVICE_NAME = process.env.OTEL_SERVICE_NAME || 'gateway-api';
const METRICS_PORT = Number(process.env.PROMETHEUS_METRICS_PORT) || 9464;

let started = false;

export function configureTelemetry(): void {
  if (started) {
    return;
  }
  started = true;

  type SdkInstance = { start(): void; shutdown(): Promise<void> };
  type NodeSDKCtor = new (opts: {
    resource: unknown;
    metricReader: unknown;
    instrumentations: unknown[];
  }) => SdkInstance;
  type GetNodeAutoInstrumentations = () => unknown[];
  type PrometheusExporterCtor = new (opts: { port: number }) => unknown;
  type ResourceCtor = new (attrs: Record<string, string>) => unknown;

  // Definite-assignment assertions: all five are set inside the try block;
  // execution reaches past the try only when all assignments succeeded.
  let NodeSDK!: NodeSDKCtor;
  let getNodeAutoInstrumentations!: GetNodeAutoInstrumentations;
  let PrometheusExporter!: PrometheusExporterCtor;
  let Resource!: ResourceCtor;
  let SEMRESATTRS_SERVICE_NAME!: string;

  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    ({ NodeSDK } = require('@opentelemetry/sdk-node'));
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    ({ getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node'));
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    ({ PrometheusExporter } = require('@opentelemetry/exporter-prometheus'));
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    ({ Resource } = require('@opentelemetry/resources'));
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    ({ SEMRESATTRS_SERVICE_NAME } = require('@opentelemetry/semantic-conventions'));
  } catch {
    // OpenTelemetry packages not installed — telemetry is disabled.
    return;
  }

  const prometheusExporter = new PrometheusExporter({ port: METRICS_PORT });

  const sdk = new NodeSDK({
    resource: new Resource({ [SEMRESATTRS_SERVICE_NAME]: SERVICE_NAME }),
    metricReader: prometheusExporter,
    instrumentations: [getNodeAutoInstrumentations()],
  });

  sdk.start();

  const shutdown = (): void => {
    sdk
      .shutdown()
      .catch(() => undefined)
      .finally(() => process.exit(0));
  };
  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
}
