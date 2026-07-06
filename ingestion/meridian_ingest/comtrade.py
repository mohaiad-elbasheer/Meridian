"""UN Comtrade ingestor: annual bilateral import values (trade-network structure).

Feeds the country dependency layer: with TOTAL imports by partner we can turn the
curated import-share edges into data-derived ones. Free API key required
(COMTRADE_API_KEY in .env, from comtradeapi.un.org).

Endpoint: GET https://comtradeapi.un.org/data/v1/get/C/A/HS
  ?reporterCode=<M49>&period=<year>&flowCode=M&cmdCode=TOTAL&partnerCode=<all>
  header: Ocp-Apim-Subscription-Key

CLI:  python -m meridian_ingest.comtrade [--year 2025] [--reporters ITA,DEU,...]
"""

from __future__ import annotations

import argparse
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from . import db
from .settings import Settings

BASE_URL = "https://comtradeapi.un.org/data/v1/get/C/A/HS"

# Default reporter set: countries carrying import-dependency edges in the seed.
DEFAULT_REPORTERS = ("EGY", "ITA", "GRC", "NLD", "DEU", "SAU", "JPN", "KOR", "IND",
                     "CHN", "SGP", "USA", "CHL", "PER", "ECU", "ESP", "MAR", "UKR",
                     "ROU", "BGR", "TUR", "TWN", "ZAF", "IDN", "PHL")

# Minimal ISO3 -> UN M49 numeric codes for the default reporters.
ISO3_TO_M49 = {
    "EGY": 818, "ITA": 380, "GRC": 300, "NLD": 528, "DEU": 276, "SAU": 682,
    "JPN": 392, "KOR": 410, "IND": 699, "CHN": 156, "SGP": 702, "USA": 842,
    "CHL": 152, "PER": 604, "ECU": 218, "ESP": 724, "MAR": 504, "UKR": 804,
    "ROU": 642, "BGR": 100, "TUR": 792, "TWN": 490, "ZAF": 710, "IDN": 360,
    "PHL": 608,
}


def parse_comtrade(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per (reporter, partner, year) with TOTAL import value in USD."""
    rows = []
    for rec in payload.get("data", []):
        reporter = rec.get("reporterISO")
        partner = rec.get("partnerISO")
        year = rec.get("refYear") or rec.get("period")
        if not reporter or not partner or year is None:
            continue
        rows.append({
            "reporter": reporter,
            "partner": partner,
            "year": int(year),
            "import_usd": rec.get("primaryValue"),
            "raw": rec,
        })
    return rows


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, max=30))
def fetch_reporter(client: httpx.Client, api_key: str, reporter_iso3: str,
                   year: int) -> dict[str, Any]:
    r = client.get(BASE_URL, params={
        "reporterCode": ISO3_TO_M49[reporter_iso3],
        "period": year,
        "flowCode": "M",
        "cmdCode": "TOTAL",
        "partnerCode": None,          # all partners
        "motCode": 0, "customsCode": "C00",
    }, headers={"Ocp-Apim-Subscription-Key": api_key}, timeout=120)
    r.raise_for_status()
    return r.json()


def run(year: int, reporters: tuple[str, ...] = DEFAULT_REPORTERS) -> None:
    settings = Settings()
    if not settings.comtrade_api_key:
        raise SystemExit("Set COMTRADE_API_KEY in .env (free key from comtradeapi.un.org)")
    total = 0
    with db.connect(settings.database_url) as conn, httpx.Client() as client:
        for iso3 in reporters:
            payload = fetch_reporter(client, settings.comtrade_api_key, iso3, year)
            rows = parse_comtrade(payload)
            total += db.upsert_many(conn, db.UPSERT_COUNTRY_TRADE, rows)
            print(f"comtrade/{iso3}: upserted {len(rows)} partner rows for {year}")
    print(f"comtrade: {total} rows total")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, default=2025)
    ap.add_argument("--reporters", type=str, default=",".join(DEFAULT_REPORTERS))
    args = ap.parse_args()
    run(args.year, tuple(args.reporters.split(",")))


if __name__ == "__main__":
    main()
