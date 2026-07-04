# Hosting & testing the prototype on GitHub

The prototype has three moving parts — FastAPI backend, React frontend, optional
TimescaleDB — so it cannot run on GitHub Pages (static files only). The supported
"test it on GitHub" path is **GitHub Codespaces**: a full dev environment in the
browser, free tier included (120 core-hours/month on personal accounts), with
unrestricted internet — which also makes it a good place for the first live
PortWatch ingest.

## GitHub Codespaces (recommended)

1. Merge the open PR into `main` (Codespaces default to the repo's default branch),
   or pick the PR branch in step 2.
2. On github.com → the repo → green **Code** button → **Codespaces** tab →
   **Create codespace on main**.
3. Wait for setup: the devcontainer (`.devcontainer/`) installs the Python packages
   and web dependencies automatically and prepares `.env`.
4. In the terminal, start the API:
   `uvicorn meridian_api.main:app --port 8000`
5. Second terminal (`+` in the terminal panel), start the web app:
   `cd web && npm run dev`
6. Open the **Ports** tab → globe icon next to port **5173** → the cockpit opens in
   a browser tab. Without a DB it runs on the flagged synthetic seed.
7. Full stack with database (optional but recommended):
   ```bash
   docker compose up -d db
   python -m meridian_ingest.verify_endpoints   # live check of the pinned URLs
   python -m meridian_ingest.portwatch          # first real ingest
   ```
   Restart the API afterwards — the header chip flips from SYNTHETIC SEED to
   PORTWATCH BASELINES, and saved scenarios become available.
8. Run the test suite anytime: `pytest engine/tests api/tests ingestion/tests -q`.

Stop the codespace when done (Codespaces page → ⋯ → Stop) to conserve free hours.

## What CI already covers

Every push to a PR runs GitHub Actions (`.github/workflows/ci.yml`): engine,
ingestion, and API test suites plus the production web build. Green checks on the
PR mean the code paths work; Codespaces is for *interactive* testing.

## Public hosting (later, P4)

Permanent public hosting is planned on OCI Always-Free (Docker Compose + Caddy TLS,
see `infra/oci/DEPLOY.md`), not GitHub — GitHub has no free long-running server
hosting. A limited **static demo** on GitHub Pages (pre-computed scenario results,
no live engine) is possible if a shareable teaser is wanted before P4 — ask for it.
