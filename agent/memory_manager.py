from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class MemoryManager:
    def __init__(self, db_path: str | Path, max_full_episodes: int = 5) -> None:
        self.db_path = Path(db_path)
        self.max_full_episodes = max_full_episodes
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    content TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    def write(self, key: str, value: Any, timestamp: float | None = None) -> None:
        if timestamp is None:
            timestamp = time.time()

        payload = json.dumps(value, sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (key, payload, timestamp)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    payload = excluded.payload,
                    timestamp = excluded.timestamp
                """,
                (key, payload, timestamp),
            )

        self._compress_if_needed()

    def read(self, key: str) -> Any | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM memories WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload"])

    def get_full_episodes(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT key, payload, timestamp FROM memories ORDER BY timestamp ASC"
            ).fetchall()

        return [
            {
                "key": row["key"],
                "value": json.loads(row["payload"]),
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def get_summary(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT content FROM summaries WHERE id = 1"
            ).fetchone()
        if row is None:
            return None
        return row["content"]

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        query_lower = query.lower()
        now = time.time()
        results: list[dict[str, Any]] = []

        for episode in self.get_full_episodes():
            searchable = f'{episode["key"]} {json.dumps(episode["value"], sort_keys=True)}'.lower()
            if query_lower not in searchable:
                continue

            age_seconds = max(now - float(episode["timestamp"]), 0.0)
            recency_score = 1.0 / (1.0 + age_seconds)
            confidence = recency_score + 1.0
            results.append({**episode, "confidence": confidence})

        results.sort(key=lambda item: item["confidence"], reverse=True)
        return results[:top_k]

    def _compress_if_needed(self) -> None:
        while True:
            with self._connect() as connection:
                count_row = connection.execute(
                    "SELECT COUNT(*) AS count FROM memories"
                ).fetchone()
                current_count = int(count_row["count"])

                if current_count <= self.max_full_episodes:
                    return

                surplus = current_count - self.max_full_episodes
                rows = connection.execute(
                    """
                    SELECT key, payload, timestamp
                    FROM memories
                    ORDER BY timestamp ASC
                    LIMIT ?
                    """,
                    (surplus,),
                ).fetchall()

                episodes = [
                    {
                        "key": row["key"],
                        "value": json.loads(row["payload"]),
                        "timestamp": row["timestamp"],
                    }
                    for row in rows
                ]

                if not episodes:
                    return

                summary_chunk = self._summarize_episodes(episodes)
                existing_summary = self.get_summary()
                combined_summary = (
                    f"{existing_summary}\n{summary_chunk}" if existing_summary else summary_chunk
                )

                connection.execute(
                    """
                    INSERT INTO summaries (id, content, updated_at)
                    VALUES (1, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        content = excluded.content,
                        updated_at = excluded.updated_at
                    """,
                    (combined_summary, time.time()),
                )

                connection.executemany(
                    "DELETE FROM memories WHERE key = ?",
                    [(episode["key"],) for episode in episodes],
                )

    def _summarize_episodes(self, episodes: list[dict[str, Any]]) -> str:
        lines = []
        for episode in episodes:
            lines.append(f'{episode["key"]}: {json.dumps(episode["value"], sort_keys=True)}')
        return "\n".join(lines)
