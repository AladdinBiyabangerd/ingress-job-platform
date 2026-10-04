# Railway builds this when the api service root is api/.
# Same idea as ingress-academy's Dockerfile: Python image, install deps, serve on $PORT.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8010

WORKDIR /app

COPY pyproject.toml .
COPY app ./app
RUN pip install .

EXPOSE 8010

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8010}"]
