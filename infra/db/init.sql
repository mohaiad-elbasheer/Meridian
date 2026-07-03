CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS chokepoint_daily (
  chokepoint_id TEXT NOT NULL,
  date DATE NOT NULL,
  transit_calls INTEGER,
  trade_tons DOUBLE PRECISION,
  vessel_breakdown JSONB,
  raw JSONB NOT NULL,
  ingested_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (chokepoint_id, date)
);
SELECT create_hypertable('chokepoint_daily', 'date', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS port_daily (
  port_id TEXT NOT NULL,
  date DATE NOT NULL,
  portcalls INTEGER,
  import_tons DOUBLE PRECISION,
  export_tons DOUBLE PRECISION,
  raw JSONB NOT NULL,
  ingested_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (port_id, date)
);
SELECT create_hypertable('port_daily', 'date', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS geo_events (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,          -- gdelt | usgs | gdacs
  event_time TIMESTAMPTZ NOT NULL,
  category TEXT,
  severity DOUBLE PRECISION,
  lon DOUBLE PRECISION,
  lat DOUBLE PRECISION,
  raw JSONB NOT NULL,
  ingested_at TIMESTAMPTZ DEFAULT now()
);
