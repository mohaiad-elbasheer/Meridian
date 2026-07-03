"""GDELT 2.0 events ingestor (15-minute cadence geopolitical signal).

Poll http://data.gdeltproject.org/gdeltv2/lastupdate.txt -> latest export CSV zip URL.
P0 scope: filter to conflict/protest/sanction-relevant CAMEO root codes near maritime
chokepoint bounding boxes; store event counts per chokepoint region per 15-min window.
Keep it aggregate — do not store personal-level data.
"""

LASTUPDATE_URL = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

# TODO(P0): implement fetch -> filter -> aggregate -> upsert
