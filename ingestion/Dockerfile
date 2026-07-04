# Multi-arch base (works on OCI Ampere A1 / arm64).
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY meridian_ingest ./meridian_ingest
RUN pip install --no-cache-dir .

CMD ["python", "-m", "meridian_ingest.scheduler"]
