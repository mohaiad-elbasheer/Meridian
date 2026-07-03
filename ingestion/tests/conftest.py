import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def chokepoints_page() -> dict:
    return json.loads((FIXTURES / "chokepoints_page.json").read_text())


@pytest.fixture
def ports_page() -> dict:
    return json.loads((FIXTURES / "ports_page.json").read_text())


@pytest.fixture
def usgs_feed() -> dict:
    return json.loads((FIXTURES / "usgs_feed.json").read_text())


@pytest.fixture
def gdacs_rss() -> str:
    return (FIXTURES / "gdacs_rss.xml").read_text()
