"""One-shot first fill: run every ingestor once, continue past individual failures.

CLI:  python -m meridian_ingest.run_all
Exit code 0 = everything succeeded; 1 = at least one source failed (details printed).
Comtrade is attempted only when COMTRADE_API_KEY is set.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime, timezone

from . import comtrade, gdelt, hazards, portwatch
from .settings import Settings


def main() -> None:
    settings = Settings()
    jobs = [
        ("portwatch (chokepoints + ports)", lambda: portwatch.ingest("all")),
        ("gdelt", gdelt.run),
        ("hazards (usgs + gdacs)", lambda: hazards.run("all")),
    ]
    if settings.comtrade_api_key:
        year = datetime.now(timezone.utc).year - 1
        jobs.append((f"comtrade ({year})", lambda: comtrade.run(year)))
    else:
        print("comtrade: skipped (COMTRADE_API_KEY not set — free key from comtradeapi.un.org)")

    failures = []
    for name, job in jobs:
        print(f"== {name} ==")
        try:
            job()
        except SystemExit as exc:      # ingestors use SystemExit for config errors
            failures.append((name, str(exc)))
            print(f"FAILED {name}: {exc}")
        except Exception as exc:  # noqa: BLE001 — keep filling other sources
            failures.append((name, str(exc)))
            print(f"FAILED {name}: {exc}")
            traceback.print_exc()

    if failures:
        print(f"\n{len(failures)} source(s) failed: " + ", ".join(n for n, _ in failures))
        sys.exit(1)
    print("\nall sources ingested")


if __name__ == "__main__":
    main()
