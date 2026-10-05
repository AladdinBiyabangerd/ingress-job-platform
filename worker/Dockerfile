# One collector pass, then exit. Railway cron starts this every hour.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    CV_OCR_ENABLED=1 \
    CV_OCR_LANG=eng

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY worker ./worker
RUN pip install .

CMD ["python", "-m", "worker"]
