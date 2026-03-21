"""Tests for state file management."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paywallfetcher import state as state_mod
from paywallfetcher.errors import StateError


def test_load_missing_returns_empty():
    s = state_mod.load("/nonexistent/path/_state.json")
    assert s["version"] == 2
    assert s["articles"] == {}
    assert s["qa"] == {}


def test_save_and_reload(tmp_path):
    path = str(tmp_path / "_state.json")
    s = state_mod._empty()
    state_mod.record_article(s, "art_001", title="Test Article")
    state_mod.mark_run(s)
    state_mod.save(path, s)

    reloaded = state_mod.load(path)
    assert "art_001" in reloaded["articles"]
    assert reloaded["articles"]["art_001"]["title"] == "Test Article"
    assert reloaded["last_successful_run_at"] is not None


def test_atomic_write_does_not_leave_tmp(tmp_path):
    path = str(tmp_path / "_state.json")
    s = state_mod._empty()
    state_mod.save(path, s)
    tmp = tmp_path / "_state.tmp"
    assert not tmp.exists()


def test_migrate_v1_to_v2():
    v1 = {"downloaded": ["id1", "id2"], "last_run": "2026-01-01T00:00:00"}
    migrated = state_mod._migrate(v1)
    assert migrated["version"] == 2
    assert "id1" in migrated["articles"]
    assert "id2" in migrated["articles"]
    assert migrated["last_successful_run_at"] == "2026-01-01T00:00:00"


def test_downloaded_ids(tmp_path):
    s = state_mod._empty()
    state_mod.record_article(s, "a1")
    state_mod.record_article(s, "a2")
    assert state_mod.downloaded_article_ids(s) == {"a1", "a2"}


def test_corrupted_state_raises_state_error(tmp_path):
    path = tmp_path / "_state.json"
    path.write_text("not valid json", encoding="utf-8")
    with pytest.raises(StateError):
        state_mod.load(str(path))
