# Build context is api/ (Railway rootDirectory = api).
# CV parse needs the worker package; install it from this repo at the same commit.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8010 \
    CV_OCR_ENABLED=1 \
    CV_OCR_LANG=eng

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY app ./app
RUN pip install .

# Same commit as this deploy so API and worker.cv_parse stay in sync.
ARG RAILWAY_GIT_COMMIT_SHA=main
RUN pip install \
    "git+https://github.com/AladdinBiyabangerd/ingress-job-platform.git@${RAILWAY_GIT_COMMIT_SHA}#subdirectory=worker"

EXPOSE 8010

# :: = all interfaces (IPv4+IPv6). Required for Railway private networking on
# legacy IPv6-only environments; 0.0.0.0 alone is unreachable there.
CMD ["sh", "-c", "exec uvicorn app.main:app --host :: --port ${PORT:-8010}"]
