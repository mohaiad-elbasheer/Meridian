#!/usr/bin/env bash
# Codespaces / devcontainer bootstrap: install all packages, prepare .env.
# The universal image ships python, node, and docker — no devcontainer features
# needed (feature installs were the failure point of the previous config).
set -euo pipefail

python -m pip install -e "./engine[dev]" -e "./api[dev]" -e "./ingestion[dev]"
(cd web && npm install)

if [ ! -f .env ]; then
  cp .env.example .env
  # Inside the devcontainer the DB runs via docker compose on localhost.
  sed -i 's/@db:5432/@localhost:5432/' .env
fi

echo
echo "Meridian devcontainer ready."
echo "  API:      uvicorn meridian_api.main:app --port 8000"
echo "  Web:      cd web && npm run dev"
echo "  DB:       docker compose up -d db   (then: python -m meridian_ingest.verify_endpoints)"
echo "  Tests:    pytest engine/tests api/tests ingestion/tests -q"
