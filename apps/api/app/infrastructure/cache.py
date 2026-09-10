"""Small persistent SQLite cache for normalized external-data payloads."""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

_SCHEMA_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class CacheEntry:
    payload: str
    retrieved_at: datetime
    content_hash: str


@dataclass(frozen=True, slots=True)
class PriceCacheEntry(CacheEntry):
    provider: str
    asset_id: str
    frequency: str
    price_field: str
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class CacheMetrics:
    hits: int
    misses: int
    writes: int
    corruptions: int


class SQLiteCache:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._metrics_lock = threading.Lock()
        self._initialized = False
        self._hits = self._misses = self._writes = self._corruptions = 0

    @property
    def metrics(self) -> CacheMetrics:
        with self._metrics_lock:
            return CacheMetrics(self._hits, self._misses, self._writes, self._corruptions)

    def _record(self, field: str) -> None:
        with self._metrics_lock:
            setattr(self, field, getattr(self, field) + 1)

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=30)
        connection.execute("PRAGMA busy_timeout=30000")
        if self._initialized:
            return connection
        with _SCHEMA_LOCK:
            if self._initialized:
                return connection
            if connection.execute("PRAGMA journal_mode").fetchone()[0].lower() != "wal":
                connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
            CREATE TABLE IF NOT EXISTS external_cache (
                namespace TEXT NOT NULL,
                cache_key TEXT NOT NULL,
                payload TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                PRIMARY KEY (namespace, cache_key)
            )
            """
            )
            connection.execute(
                """
            CREATE TABLE IF NOT EXISTS price_series_cache (
                provider TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                frequency TEXT NOT NULL,
                price_field TEXT NOT NULL,
                coverage_start TEXT NOT NULL,
                coverage_end TEXT NOT NULL,
                payload TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                PRIMARY KEY (
                    provider, asset_id, frequency, price_field,
                    coverage_start, coverage_end
                )
            )
            """
            )
            connection.execute(
                """
            CREATE INDEX IF NOT EXISTS price_series_covering
            ON price_series_cache (
                provider, asset_id, frequency, price_field,
                coverage_start, coverage_end, retrieved_at
            )
            """
            )
            connection.commit()
            self._initialized = True
            return connection

    def get(self, namespace: str, cache_key: str) -> CacheEntry | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT payload, retrieved_at, content_hash FROM external_cache "
                "WHERE namespace = ? AND cache_key = ?",
                (namespace, cache_key),
            ).fetchone()
        if row is None:
            return None
        retrieved_at = datetime.fromisoformat(row[1])
        if retrieved_at.tzinfo is None:
            retrieved_at = retrieved_at.replace(tzinfo=UTC)
        return CacheEntry(row[0], retrieved_at, row[2])

    def put(
        self,
        namespace: str,
        cache_key: str,
        payload: str,
        retrieved_at: datetime,
        content_hash: str,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO external_cache
                    (namespace, cache_key, payload, retrieved_at, content_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (namespace, cache_key, payload, retrieved_at.isoformat(), content_hash),
            )
            connection.commit()

    def get_covering_price_series(
        self,
        provider: str,
        asset_id: str,
        frequency: str,
        price_field: str,
        start: date,
        end: date,
        *,
        not_before: datetime | None,
    ) -> PriceCacheEntry | None:
        """Return the newest intact snapshot that fully covers the requested interval."""

        parameters: list[str] = [
            provider,
            asset_id,
            frequency,
            price_field,
            start.isoformat(),
            end.isoformat(),
        ]
        freshness = ""
        if not_before is not None:
            freshness = " AND retrieved_at >= ?"
            parameters.append(not_before.astimezone(UTC).isoformat())
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT coverage_start, coverage_end, payload, retrieved_at, content_hash "
                "FROM price_series_cache WHERE provider=? AND asset_id=? "
                "AND frequency=? AND price_field=? AND coverage_start<=? AND coverage_end>=?"
                + freshness
                + " ORDER BY retrieved_at DESC, coverage_start DESC, coverage_end ASC",
                parameters,
            ).fetchall()
            for row in rows:
                if hashlib.sha256(row[2].encode()).hexdigest() == row[4]:
                    self._record("_hits")
                    retrieved_at = datetime.fromisoformat(row[3])
                    if retrieved_at.tzinfo is None:
                        retrieved_at = retrieved_at.replace(tzinfo=UTC)
                    return PriceCacheEntry(
                        row[2],
                        retrieved_at,
                        row[4],
                        provider,
                        asset_id,
                        frequency,
                        price_field,
                        date.fromisoformat(row[0]),
                        date.fromisoformat(row[1]),
                    )
                self._record("_corruptions")
                connection.execute(
                    "DELETE FROM price_series_cache WHERE provider=? AND asset_id=? "
                    "AND frequency=? AND price_field=? AND coverage_start=? AND coverage_end=?",
                    (provider, asset_id, frequency, price_field, row[0], row[1]),
                )
            connection.commit()
        self._record("_misses")
        return None

    def put_price_series(
        self,
        provider: str,
        asset_id: str,
        frequency: str,
        price_field: str,
        start: date,
        end: date,
        payload: str,
        retrieved_at: datetime,
    ) -> None:
        content_hash = hashlib.sha256(payload.encode()).hexdigest()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT OR REPLACE INTO price_series_cache
                    (provider, asset_id, frequency, price_field, coverage_start,
                     coverage_end, payload, retrieved_at, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider,
                    asset_id,
                    frequency,
                    price_field,
                    start.isoformat(),
                    end.isoformat(),
                    payload,
                    retrieved_at.astimezone(UTC).isoformat(),
                    content_hash,
                ),
            )
            # The new snapshot dominates older snapshots wholly contained by it.
            connection.execute(
                """
                DELETE FROM price_series_cache
                WHERE provider=? AND asset_id=? AND frequency=? AND price_field=?
                  AND coverage_start>=? AND coverage_end<=? AND retrieved_at<=?
                  AND NOT (coverage_start=? AND coverage_end=? AND retrieved_at=?)
                """,
                (
                    provider,
                    asset_id,
                    frequency,
                    price_field,
                    start.isoformat(),
                    end.isoformat(),
                    retrieved_at.astimezone(UTC).isoformat(),
                    start.isoformat(),
                    end.isoformat(),
                    retrieved_at.astimezone(UTC).isoformat(),
                ),
            )
            connection.commit()
        self._record("_writes")

    def delete_price_series(self, entry: PriceCacheEntry) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "DELETE FROM price_series_cache WHERE provider=? AND asset_id=? "
                "AND frequency=? AND price_field=? AND coverage_start=? AND coverage_end=?",
                (
                    entry.provider,
                    entry.asset_id,
                    entry.frequency,
                    entry.price_field,
                    entry.start.isoformat(),
                    entry.end.isoformat(),
                ),
            )
            connection.commit()
        self._record("_corruptions")

    def prune_price_series(self, provider: str, *, older_than: datetime) -> int:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "DELETE FROM price_series_cache WHERE provider=? AND retrieved_at<?",
                (provider, older_than.astimezone(UTC).isoformat()),
            )
            connection.commit()
            return cursor.rowcount
