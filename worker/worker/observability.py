"""Sentry and OpenTelemetry for the collector. Off when unset.

Sentry uses the same variables as ingress-academy and the job API.
Academy has no OpenTelemetry setup; spans export only when
OTEL_EXPORTER_OTLP_ENDPOINT is set.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager

log = logging.getLogger("ingress-job.worker.observability")
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

    sentry_sdk.init(
        dsn=dsn,
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


@contextmanager
def span(name: str):
    if not _otel_ready:
        yield
        return
    from opentelemetry import trace

    with trace.get_tracer("ingress-job-worker").start_as_current_span(name):
        yield


def capture_exception() -> None:
    if not os.environ.get("SENTRY_DSN", "").strip():
        return
    import sentry_sdk

    sentry_sdk.capture_exception()


def flush() -> None:
    if not _otel_ready:
        return
    from opentelemetry import trace

    provider = trace.get_tracer_provider()
    force_flush = getattr(provider, "force_flush", None)
    if force_flush is not None:
        force_flush(timeout_millis=5000)
