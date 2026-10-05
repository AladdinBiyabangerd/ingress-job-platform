# Build context is the repository root (see .railway/railway.ts).
# Installs the API plus the worker package so CV parse can run in-process.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8010 \
    CV_OCR_ENABLED=1 \
    CV_OCR_LANG=eng

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY api/pyproject.toml ./api/
COPY api/app ./api/app
COPY worker/pyproject.toml ./worker/
COPY worker/worker ./worker/worker
RUN pip install ./api ./worker

EXPOSE 8010

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8010}"]
