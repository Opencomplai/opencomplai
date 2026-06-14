"""
OpenTelemetry instrumentation helpers shared across Python services.

Provides:
- The canonical PRD Section 11.1 telemetry event names as constants.
- ``configure_telemetry()`` — wires up the OTel SDK from environment variables.
- ``emit_event()`` — records a span and increments a Prometheus counter.
- ``get_meter()`` — returns a configured OTel ``Meter``.
- ``metrics_response()`` — produces a FastAPI Prometheus ``/metrics`` response.

All entry points are graceful no-ops if the optional OpenTelemetry / Prometheus
client packages are not installed, so importing this module never fails and
services can boot without telemetry in air-gapped or stripped-down environments.
"""

from __future__ import annotations

import os
from typing import Any

# ---------------------------------------------------------------------------
# PRD Section 11.1 telemetry event names (canonical — never deviate)
# ---------------------------------------------------------------------------
EVENT_COMPLIANCE_CHECK_STARTED = "compliance_check_started"
EVENT_COMPLIANCE_CHECK_COMPLETED = "compliance_check_completed"
EVENT_TRAP_DETECTED = "trap_detected"
EVENT_OVERRIDE_SUBMITTED = "override_submitted"
EVENT_VERIFICATION_FAILED = "verification_failed"
EVENT_DOSSIER_GENERATED = "dossier_generated"
EVENT_EGRESS_BLOCKED = "egress_blocked"
EVENT_INSTALL_COMPLETED = "install_completed"
EVENT_FIRST_SCAN_COMPLETED = "first_scan_completed"
EVENT_BADGE_ISSUED = "badge_issued"

ALL_EVENTS: tuple[str, ...] = (
    EVENT_COMPLIANCE_CHECK_STARTED,
    EVENT_COMPLIANCE_CHECK_COMPLETED,
    EVENT_TRAP_DETECTED,
    EVENT_OVERRIDE_SUBMITTED,
    EVENT_VERIFICATION_FAILED,
    EVENT_DOSSIER_GENERATED,
    EVENT_EGRESS_BLOCKED,
    EVENT_INSTALL_COMPLETED,
    EVENT_FIRST_SCAN_COMPLETED,
    EVENT_BADGE_ISSUED,
)


def _try_import_otel() -> tuple[Any, Any]:
    """Return (trace, metrics) modules if available, else (None, None)."""
    try:
        from opentelemetry import metrics, trace  # type: ignore[import-not-found]

        return trace, metrics
    except ImportError:
        return None, None


def configure_telemetry(service_name: str) -> None:
    """
    Configure the OpenTelemetry SDK for a Python service.

    Reads the following environment variables:
      OTEL_SERVICE_NAME            — overrides ``service_name`` if set
      OTEL_EXPORTER_OTLP_ENDPOINT  — optional gRPC OTLP endpoint for traces

    No-op when ``opentelemetry`` is not installed.
    """
    trace, metrics = _try_import_otel()
    if trace is None or metrics is None:
        return

    try:
        from opentelemetry.sdk.resources import (  # type: ignore[import-not-found]
            SERVICE_NAME,
            Resource,
        )
        from opentelemetry.sdk.trace import (
            TracerProvider,  # type: ignore[import-not-found]
        )
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,  # type: ignore[import-not-found]
        )
    except ImportError:
        return

    resource = Resource.create(
        {SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", service_name)}
    )

    tracer_provider = TracerProvider(resource=resource)

    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-not-found]
                OTLPSpanExporter,
            )

            tracer_provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
            )
        except ImportError:
            pass

    trace.set_tracer_provider(tracer_provider)

    try:
        from opentelemetry.exporter.prometheus import (
            PrometheusMetricReader,  # type: ignore[import-not-found]
        )
        from opentelemetry.sdk.metrics import (
            MeterProvider,  # type: ignore[import-not-found]
        )

        reader = PrometheusMetricReader()
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)
    except ImportError:
        pass


def get_meter(service_name: str) -> Any:
    """Return an OTel ``Meter`` or ``None`` if OpenTelemetry is unavailable."""
    _trace, metrics = _try_import_otel()
    if metrics is None:
        return None
    return metrics.get_meter(service_name)


def emit_event(
    event_type: str,
    attributes: dict[str, Any] | None = None,
    meter: Any | None = None,
) -> None:
    """
    Emit a PRD Section 11.1 telemetry event.

    Records a trace span carrying ``attributes`` and increments the Prometheus
    counter ``opencomplai_<event_type>_total``. Both operations are best-effort:
    if OpenTelemetry isn't installed, this is a silent no-op so calling code
    can sprinkle ``emit_event`` calls without worrying about deployment shape.
    """
    attrs = attributes or {}
    trace, _metrics = _try_import_otel()
    if trace is not None:
        try:
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(event_type, attributes=attrs):
                pass
        except Exception:
            pass

    if meter is not None:
        try:
            counter = meter.create_counter(
                name=f"opencomplai_{event_type}_total",
                description=f"Total count of {event_type} events",
            )
            counter.add(1, attrs)
        except Exception:
            pass


def metrics_response() -> Any:
    """
    Build a FastAPI ``Response`` containing the Prometheus text exposition.

    Returns ``None`` if ``prometheus_client`` is not installed, so callers can
    branch on the result and return 503 if desired.
    """
    try:
        from fastapi.responses import Response  # type: ignore[import-not-found]
        from prometheus_client import (  # type: ignore[import-not-found]
            CONTENT_TYPE_LATEST,
            generate_latest,
        )
    except ImportError:
        return None

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
