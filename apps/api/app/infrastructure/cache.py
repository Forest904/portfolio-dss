"""Small persistent SQLite cache for normalized external-data payloads."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CacheEntry:
    payload: str
    retrieved_at: datetime
    content_hash: str


class SQLiteCache:
    def __init__(self, path: Path) -> None:
        self._path = path

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path)
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
