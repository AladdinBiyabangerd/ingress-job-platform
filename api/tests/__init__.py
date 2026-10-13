"""Enable parked product surfaces for the API unit suite."""

import os

os.environ.setdefault("PRODUCT_RECOMMENDATIONS_ENABLED", "1")
os.environ.setdefault("PRODUCT_ROADMAP_ENABLED", "1")
os.environ.setdefault("PRODUCT_EMPLOYER_POSTING_ENABLED", "1")

# Isolation: never let real provider / mail / DB credentials from the
# developer shell leak into unit tests (real 401s, real SMTP, real Postgres).
for _key in list(os.environ):
    if _key.endswith("_API_KEY") or _key in {
        "DATABASE_URL", "REDIS_URL", "AI_CHAT_PROVIDERS", "AI_EMBED_PROVIDERS",
        "EMAIL_HOST", "EMAIL_PORT", "EMAIL_HOST_USER", "EMAIL_HOST_PASSWORD",
        "EMAIL_USE_TLS", "EMAIL_USE_SSL", "DEFAULT_FROM_EMAIL", "JOB_IMPORT_TOKEN",
    }:
        os.environ.pop(_key, None)
