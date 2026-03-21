"""State file management.

Uses atomic rename for writes (write to .tmp then replace).
Not safe for concurrent write access — single-writer assumption.
State schema v2:
  {
    "version": 2,
    "articles": {
      "<id>": {
        "first_seen_at": "...",
        "last_downloaded_at": "...",
        "title": "...",
        "content_hash": ""
      }
    },
    "qa": {
      "<id>": {
        "first_seen_at": "...",
        "last_downloaded_at": "...",
        "question": "...",
        "answer_status": "present|empty|blocked|unknown"
      }
    },
    "last_successful_run_at": "...",
    "last_scan_cursor": {}
  }
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Set

from .errors import StateError

_STATE_VERSION = 2


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load(state_path: str) -> Dict[str, Any]:
    """Load state from file. Returns empty v2 state if file does not exist."""
    path = Path(state_path)
    if not path.exists():
        return _empty()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return _migrate(data)
    except Exception as exc:
        raise StateError(f"Failed to read state file {state_path}: {exc}") from exc


def save(state_path: str, state: Dict[str, Any]) -> None:
    """Write state atomically (write to .tmp then replace)."""
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise StateError(f"Failed to write state file {state_path}: {exc}") from exc


def record_article(state: Dict[str, Any], article_id: str, title: str = "", content_hash: str = "") -> None:
    now = _now()
    entry = state["articles"].setdefault(article_id, {"first_seen_at": now})
    entry["last_downloaded_at"] = now
    if title:
        entry["title"] = title
    if content_hash:
        entry["content_hash"] = content_hash


def record_qa(state: Dict[str, Any], qa_id: str, question: str = "", answer_status: str = "unknown") -> None:
    now = _now()
    entry = state["qa"].setdefault(qa_id, {"first_seen_at": now})
    entry["last_downloaded_at"] = now
    if question:
        entry["question"] = question
    entry["answer_status"] = answer_status


def mark_run(state: Dict[str, Any]) -> None:
    state["last_successful_run_at"] = _now()


def downloaded_article_ids(state: Dict[str, Any]) -> Set[str]:
    return set(state.get("articles", {}).keys())


def downloaded_qa_ids(state: Dict[str, Any]) -> Set[str]:
    return set(state.get("qa", {}).keys())


def _empty() -> Dict[str, Any]:
    return {
        "version": _STATE_VERSION,
        "articles": {},
        "qa": {},
        "last_successful_run_at": None,
        "last_scan_cursor": {},
    }


def _migrate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate v1 (list-based) state to v2 (dict-based)."""
    if data.get("version") == _STATE_VERSION:
        return data

    state = _empty()
    now = _now()

    for aid in data.get("downloaded", []):
        state["articles"][str(aid)] = {"first_seen_at": now, "last_downloaded_at": now}

    if "last_run" in data:
        state["last_successful_run_at"] = data["last_run"]

    return state
