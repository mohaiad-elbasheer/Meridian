FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY api/pyproject.toml ./api/pyproject.toml
COPY api/meridian_api ./api/meridian_api
COPY engine/pyproject.toml ./engine/pyproject.toml
COPY engine/meridian_engine ./engine/meridian_engine

RUN pip install --upgrade pip \
    && pip install --no-cache-dir ./engine \
    && pip install --no-cache-dir ./api

EXPOSE 8000

CMD ["uvicorn", "meridian_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
