"""Sentry and OpenTelemetry. Both stay off when their settings are absent.

Sentry matches ingress-academy config/settings.py: init only when SENTRY_DSN
is set, send_default_pii is false, SENTRY_TRACES_SAMPLE_RATE defaults to 0.0,
and SENTRY_ENVIRONMENT falls back from DEBUG.

Academy does not initialize OpenTelemetry. Traces are exported only when
OTEL_EXPORTER_OTLP_ENDPOINT is set, using the OpenTelemetry SDK variable names,
because Academy defines none.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("ingress-job.observability")
_otel_ready = False


def _debug() -> bool:
    raw = os.environ.get("DEBUG")
    if raw is None or not raw.strip():
        return True
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def init_sentry() -> None:
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        send_default_pii=False,
        environment=os.environ.get(
            "SENTRY_ENVIRONMENT",
            "production" if not _debug() else "development",
        ),
    )


def init_otel(service_name: str) -> None:
    global _otel_ready
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    disabled = os.environ.get("OTEL_SDK_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    if not endpoint or disabled or _otel_ready:
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

    ratio = float(os.environ.get("OTEL_TRACES_SAMPLER_ARG", "1.0"))
    name = os.environ.get("OTEL_SERVICE_NAME", "").strip() or service_name
    provider = TracerProvider(
        resource=Resource.create({"service.name": name}),
        sampler=ParentBased(TraceIdRatioBased(min(max(ratio, 0.0), 1.0))),
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(timeout=5), export_timeout_millis=5000)
    )
    trace.set_tracer_provider(provider)
    _otel_ready = True


def init_observability(service_name: str) -> None:
    init_sentry()
    try:
        init_otel(service_name)
    except Exception:
        log.warning("OpenTelemetry was not started")


def otel_enabled() -> bool:
    return _otel_ready
