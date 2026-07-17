# Build from the REPO ROOT (compose sets context: .) — the API installs the local
# meridian-engine package, which lives outside api/.
# Multi-arch base (works on OCI Ampere A1 / arm64).
FROM python:3.12-slim

WORKDIR /app
COPY engine/pyproject.toml engine/pyproject.toml
COPY engine/meridian_engine engine/meridian_engine
COPY api/pyproject.toml api/pyproject.toml
COPY api/meridian_api api/meridian_api
RUN pip install --no-cache-dir ./engine ./api

EXPOSE 8000
CMD ["uvicorn", "meridian_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
