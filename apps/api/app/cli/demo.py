"""Offline API entry point: uv run uvicorn app.cli.demo:app --port 8011."""

from pathlib import Path
from tempfile import gettempdir

from app.core.config import Settings
from app.infrastructure.demo import (
    DEMO_NOW,
    DemoDataProvider,
    DemoGuidedFactory,
    DemoUniverseProvider,
)
from app.infrastructure.guided_jobs import ProcessGuidedJobs, SQLiteGuidedRepository
from app.main import create_app

runtime = Path(gettempdir()) / "portfolio-dss-offline-demo"
jobs_path = runtime / "guided_jobs.sqlite3"

app = create_app(
    settings=Settings(runtime / "market_data.sqlite3"),
    universe_provider=DemoUniverseProvider(),
    market_data_provider=DemoDataProvider(),
    clock=lambda: DEMO_NOW,
    guided_jobs=ProcessGuidedJobs(
        SQLiteGuidedRepository(jobs_path), DemoGuidedFactory(), lambda: "synthetic-demo-v1"
    ),
)
