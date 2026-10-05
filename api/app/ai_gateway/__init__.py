"""Shared AI gateway: redact, cache, budget, cost log, provider calls."""

from __future__ import annotations

from app.ai_gateway.gateway import (
    EmbedResult,
    GatewayResult,
    complete_json,
    daily_call_limit,
    embed,
    embedding_model_name,
    enabled,
    ensure_ai_tables,
    model_name,
)
from app.ai_gateway.redact import mask_pii

__all__ = [
    "EmbedResult",
    "GatewayResult",
    "complete_json",
    "daily_call_limit",
    "embed",
    "embedding_model_name",
    "enabled",
    "ensure_ai_tables",
    "mask_pii",
    "model_name",
]
