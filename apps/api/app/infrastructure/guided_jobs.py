"""SQLite jobs and one supervised, terminable calculation process.

Pickled model objects are internal cache records written only by this application,
never accepted from API clients. The database is a trusted local application file.
"""

import json
import multiprocessing
import pickle
import sqlite3
import sys
import threading
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, cast
from uuid import uuid4

from app.application.errors import ApplicationError, not_found
from app.application.guided import GuidedModel, GuidedRecommendationService, personalize
from app.application.guided_jobs import GuidedJob, JobFailure
from app.domain.guided import PreferenceAnswers, PreferenceResult, map_preferences

if TYPE_CHECKING:
    from app.core.config import Settings


class SQLiteGuidedRepository:
    def __init__(self, path: Path, clock: Callable[[], float] = time.time) -> None:
        self.path, self.clock = path, clock

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS guided_runs (
                    id TEXT PRIMARY KEY, request_key TEXT NOT NULL, created REAL NOT NULL,
                    stage TEXT NOT NULL, model BLOB, error TEXT);
                CREATE TABLE IF NOT EXISTS guided_jobs (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, created REAL NOT NULL,
                    preference TEXT NOT NULL, capital TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS guided_models (
                    key TEXT PRIMARY KEY, created REAL NOT NULL, model BLOB NOT NULL);
            """)

    def recover(self) -> None:
        with closing(self.connect()) as db:
            db.execute(
                "UPDATE guided_runs SET stage='failed', error=? "
                "WHERE stage NOT IN ('completed', 'failed')",
                (
                    json.dumps(
                        asdict(
                            JobFailure(
                                "JOB_INTERRUPTED",
                                "The API restarted during calculation. Please retry.",
                            )
                        )
                    ),
                ),
            )
            db.commit()

    def submit(self, key: str, preference: PreferenceResult, capital: Decimal) -> str:
        now, job_id = self.clock(), uuid4().hex
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM guided_jobs WHERE created <= ?", (now - 86400,))
            db.execute(
                "DELETE FROM guided_runs WHERE created <= ? AND stage IN ('completed','failed')",
                (now - 86400,),
            )
            db.execute("DELETE FROM guided_models WHERE created <= ?", (now - 21600,))
            run = db.execute(
                "SELECT id FROM guided_runs WHERE request_key=? "
                "AND stage NOT IN ('completed','failed')",
                (key,),
            ).fetchone()
            run_id = run["id"] if run else uuid4().hex
            if run is None:
                db.execute(
                    "INSERT INTO guided_runs VALUES (?,?,?,'queued',NULL,NULL)", (run_id, key, now)
                )
            db.execute(
                "INSERT INTO guided_jobs VALUES (?,?,?,?,?)",
                (job_id, run_id, now, json.dumps(asdict(preference)), str(capital)),
            )
            db.commit()
        return job_id

    def next_run(self) -> str | None:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT id FROM guided_runs WHERE stage='queued' ORDER BY created LIMIT 1"
            ).fetchone()
            return str(row["id"]) if row else None

    def stage(self, run_id: str, stage: str) -> None:
        with closing(self.connect()) as db:
            db.execute(
                "UPDATE guided_runs SET stage=? WHERE id=? AND stage NOT IN ('completed','failed')",
                (stage, run_id),
            )
            db.commit()

    def finish(self, run_id: str, model: GuidedModel) -> None:
        with closing(self.connect()) as db:
            db.execute(
                "UPDATE guided_runs SET stage='completed', model=? WHERE id=? "
                "AND stage NOT IN ('completed','failed')",
                (pickle.dumps(model), run_id),
            )
            db.commit()

    def fail(self, run_id: str, failure: JobFailure) -> None:
        with closing(self.connect()) as db:
            db.execute(
                "UPDATE guided_runs SET stage='failed', error=? WHERE id=? "
                "AND stage NOT IN ('completed','failed')",
                (json.dumps(asdict(failure)), run_id),
            )
            db.commit()

    def get(self, job_id: str) -> GuidedJob:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT j.*, r.stage, r.model, r.error FROM guided_jobs j "
                "JOIN guided_runs r ON r.id=j.run_id WHERE j.id=? AND j.created>?",
                (job_id, self.clock() - 86400),
            ).fetchone()
        if row is None:
            raise not_found("JOB_NOT_FOUND", "This calculation expired or does not exist.")
        stage = str(row["stage"])
        report = None
        if stage == "completed":
            stored = json.loads(row["preference"])
            preference = map_preferences(PreferenceAnswers(**stored["answers"]), stored["version"])
            report = personalize(pickle.loads(row["model"]), preference, Decimal(row["capital"]))
        return GuidedJob(
            job_id,
            stage if stage in ("queued", "completed", "failed") else "running",
            stage,
            report,
            JobFailure(**json.loads(row["error"])) if row["error"] else None,
        )

    def get_model(self, key: str) -> GuidedModel | None:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT model FROM guided_models WHERE key=? AND created>?",
                (key, self.clock() - 21600),
            ).fetchone()
        return cast(GuidedModel, pickle.loads(row["model"])) if row else None

    def put_model(self, key: str, model: GuidedModel) -> None:
        with closing(self.connect()) as db:
            db.execute(
                "INSERT OR REPLACE INTO guided_models VALUES (?,?,?)",
                (key, self.clock(), pickle.dumps(model)),
            )
            db.commit()


@dataclass(frozen=True)
class ProductionGuidedFactory:
    """Spawn-safe dependency composition; avoids importing the API in the worker."""

    settings: "Settings"

    def __call__(self, repository: SQLiteGuidedRepository) -> GuidedRecommendationService:
        from datetime import timedelta

        from app.application.frontier import PortfolioFrontierService
        from app.domain import HistoricalMeanEstimator, HistoricalSampleRiskEstimator
        from app.infrastructure.bulk_history import BoundedBulkHistoryProvider
        from app.infrastructure.cache import SQLiteCache
        from app.infrastructure.frontier import ScipyEfficientFrontierGenerator
        from app.infrastructure.wikipedia import WikipediaSP500Provider
        from app.infrastructure.yahoo import YahooFinanceMarketDataProvider

        runtime = self.settings
        cache = SQLiteCache(runtime.cache_path)
        universe = WikipediaSP500Provider(
            cache,
            timeout_seconds=runtime.provider_timeout_seconds,
            refresh_ttl=timedelta(hours=runtime.universe_cache_ttl_hours),
            stale_fallback_limit=timedelta(days=runtime.stale_fallback_days),
        )
        prices = YahooFinanceMarketDataProvider(
            cache,
            timeout_seconds=runtime.provider_timeout_seconds,
            refresh_ttl=timedelta(hours=runtime.price_cache_ttl_hours),
            stale_fallback_limit=timedelta(days=runtime.stale_fallback_days),
        )
        frontier = PortfolioFrontierService(
            universe,
            prices,
            HistoricalMeanEstimator(),
            HistoricalSampleRiskEstimator(),
            ScipyEfficientFrontierGenerator(),
            profiles=runtime.frontier_profiles,
        )
        return GuidedRecommendationService(
            universe,
            BoundedBulkHistoryProvider(prices),
            frontier,
            cache=repository,
            configuration_key=repr(runtime.frontier_profiles)
            + "historical-mean-sample-covariance-scipy-v1",
        )


GuidedFactory = Callable[[SQLiteGuidedRepository], GuidedRecommendationService]


def calculate_worker(path: Path, run_id: str, factory: GuidedFactory) -> None:
    repository = SQLiteGuidedRepository(path)
    try:
        model = factory(repository).calculate(lambda stage: repository.stage(run_id, stage))
        repository.finish(run_id, model)
    except ApplicationError as exc:
        repository.fail(run_id, JobFailure(exc.code, exc.message))
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Guided calculation failed")
        repository.fail(
            run_id,
            JobFailure("CALCULATION_FAILED", "The calculation could not finish. Please retry."),
        )


class ProcessGuidedJobs:
    def __init__(
        self,
        repository: SQLiteGuidedRepository,
        factory: GuidedFactory,
        request_key: Callable[[], str],
        *,
        timeout: float = 900,
    ) -> None:
        self.repository, self.factory = repository, factory
        self.request_key, self.timeout = request_key, timeout
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lease: BinaryIO | None = None

    def start(self) -> None:
        self.repository.initialize()
        lease = self.repository.path.with_suffix(".worker.lock").open("a+b")
        if lease.tell() == 0:
            lease.write(b"0")
            lease.flush()
        lease.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(lease.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            lease.close()
            raise RuntimeError("Guided jobs require one API process per job database") from None
        self._lease = lease
        self.repository.recover()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        if self._lease:
            self._lease.close()
            self._lease = None

    def submit(self, preference: PreferenceResult, capital: Decimal) -> str:
        return self.repository.submit(self.request_key(), preference, capital)

    def get(self, job_id: str) -> GuidedJob:
        return self.repository.get(job_id)

    def _loop(self) -> None:
        while not self._stop.is_set():
            run_id = self.repository.next_run()
            if run_id is None:
                self._stop.wait(0.2)
                continue
            process = multiprocessing.get_context("spawn").Process(
                target=calculate_worker,
                args=(self.repository.path, run_id, self.factory),
            )
            try:
                process.start()
                deadline = time.monotonic() + self.timeout
                while (
                    process.is_alive() and time.monotonic() < deadline and not self._stop.is_set()
                ):
                    process.join(timeout=0.2)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
                    if process.is_alive():
                        process.kill()
                        process.join()
                    self.repository.fail(
                        run_id,
                        JobFailure(
                            "JOB_INTERRUPTED" if self._stop.is_set() else "JOB_TIMEOUT",
                            "Calculation interrupted. Please retry."
                            if self._stop.is_set()
                            else "Calculation exceeded 15 minutes. Please retry.",
                        ),
                    )
                else:
                    self.repository.fail(
                        run_id,
                        JobFailure(
                            "WORKER_EXITED", "Calculation stopped unexpectedly. Please retry."
                        ),
                    )
            except Exception:
                self.repository.fail(
                    run_id,
                    JobFailure(
                        "WORKER_FAILED", "The calculation worker could not start. Please retry."
                    ),
                )
            finally:
                if process.pid is not None and not process.is_alive():
                    process.close()
