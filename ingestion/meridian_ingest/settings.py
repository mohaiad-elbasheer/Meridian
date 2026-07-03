from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://meridian:meridian@localhost:5432/meridian"

    # Resolve the ArcGIS FeatureServer query URLs from the "Access API" links at
    # https://portwatch.imf.org/pages/data-and-methodology and pin them here.
    # They should end with /FeatureServer/0/query
    portwatch_chokepoints_url: str = ""
    portwatch_ports_url: str = ""

    comtrade_api_key: str = ""
    fred_api_key: str = ""
