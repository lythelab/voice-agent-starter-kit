from __future__ import annotations

import time
from unittest.mock import patch

from agent.memory_manager import MemoryManager


def test_empty_db_returns_default_values(tmp_path):
    manager = MemoryManager(db_path=tmp_path / "empty.db")

    assert manager.read("missing") is None
    assert manager.get_summary() is None
    assert manager.get_full_episodes() == []


def test_memory_write_and_read(tmp_path):
    manager = MemoryManager(db_path=tmp_path / "test.db")

    manager.write("episode_1", {"action": "search", "result": "ok"})

    result = manager.read("episode_1")

    assert result["action"] == "search"
    assert result["result"] == "ok"


def test_memory_persists_after_restart(tmp_path):
    db_path = tmp_path / "test_persist.db"

    manager = MemoryManager(db_path=db_path)
    manager.write("key", {"value": 42})

    del manager

    new_manager = MemoryManager(db_path=db_path)
    result = new_manager.read("key")

    assert result["value"] == 42


def test_compression_reduces_episode_count(tmp_path):
    manager = MemoryManager(db_path=tmp_path / "test_compress.db", max_full_episodes=5)

    with patch.object(MemoryManager, "_summarize_episodes", return_value="summary"):
        for index in range(10):
            manager.write(f"episode_{index}", {"step": index, "data": "x" * 500})

    full_episodes = manager.get_full_episodes()

    assert len(full_episodes) <= 5
    assert manager.get_summary() is not None


def test_memory_confidence_weighted_by_recency(tmp_path):
    manager = MemoryManager(db_path=tmp_path / "test_confidence.db")
    now = time.time()
    old_time = now - 3600

    manager.write("old_episode", {"data": "stale"}, timestamp=old_time)
    manager.write("new_episode", {"data": "fresh"}, timestamp=now)

    results = manager.search("data", top_k=2)

    assert results[0]["key"] == "new_episode"


def test_duplicate_keys_overwrite_previous_value(tmp_path):
    manager = MemoryManager(db_path=tmp_path / "test_duplicate.db")

    manager.write("episode", {"value": 1})
    manager.write("episode", {"value": 2})

    result = manager.read("episode")

    assert result["value"] == 2
    assert len(manager.get_full_episodes()) == 1
