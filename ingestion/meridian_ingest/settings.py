from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://meridian:meridian@localhost:5432/meridian"

    # ArcGIS FeatureServer query URLs (must end with /FeatureServer/<layer>/query).
    # Pinned in .env — see .env.example. Verify with: python -m meridian_ingest.verify_endpoints
    portwatch_chokepoints_url: str = ""
    portwatch_ports_url: str = ""

    # Public feeds (not secrets — overridable for testing).
    gdelt_lastupdate_url: str = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
    usgs_feed_url: str = (
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson"
    )
    gdacs_rss_url: str = "https://www.gdacs.org/xml/rss.xml"

    comtrade_api_key: str = ""
    fred_api_key: str = ""
