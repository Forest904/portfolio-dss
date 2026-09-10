"""Synthetic-only browser QA server: uv run uvicorn tests.week8_demo:app --port 8018."""

from pathlib import Path
from tempfile import gettempdir

from app.core.config import Settings
from app.infrastructure.guided_jobs import ProcessGuidedJobs, SQLiteGuidedRepository
from app.main import create_app
from tests.guided_fixtures import FixtureFactory, fixture_clock
from tests.helpers import FakeUniverseProvider, make_universe
from tests.test_week5_api import provider

cache_path = Path(gettempdir()) / "portfolio-dss-week8-qa" / "prices.db"
app = create_app(
    settings=Settings(cache_path),
    market_data_provider=provider(),
    universe_provider=FakeUniverseProvider(make_universe("AAPL", "MSFT")),
    clock=fixture_clock,
    guided_jobs=ProcessGuidedJobs(
        SQLiteGuidedRepository(cache_path.with_name("jobs.db")),
        FixtureFactory(count=30),
        lambda: "browser-fixture",
    ),
)
