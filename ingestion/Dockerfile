# Multi-arch base (works on OCI Ampere A1 / arm64).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY ingestion/pyproject.toml ./pyproject.toml
COPY ingestion/meridian_ingest ./meridian_ingest
RUN pip install --no-cache-dir .

CMD ["python", "-m", "meridian_ingest.scheduler"]
