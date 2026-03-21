"""Tests for config loading and validation."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paywallfetcher.config import _normalize, load
from paywallfetcher.errors import ConfigError


def _write_config(tmp_path, data):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_missing_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load(str(tmp_path / "nonexistent.json"))


def test_placeholder_base_url_raises(tmp_path):
    cfg = _write_config(tmp_path, {
        "site": {"base_url": "https://example.com", "target_uid": "12345",
                 "api_paths": {}, "kind": "generic"},
        "auth": {}, "cookies": {}, "network": {}, "output": {}, "safety": {}
    })
    with pytest.raises(ConfigError, match="base_url"):
        load(cfg)


def test_placeholder_uid_raises(tmp_path):
    cfg = _write_config(tmp_path, {
        "site": {"base_url": "https://real.example.net", "target_uid": "YOUR_TARGET_UID",
                 "api_paths": {}, "kind": "generic"},
        "auth": {}, "cookies": {}, "network": {}, "output": {}, "safety": {}
    })
    with pytest.raises(ConfigError, match="placeholder"):
        load(cfg)


def test_empty_uid_raises(tmp_path):
    cfg = _write_config(tmp_path, {
        "site": {"base_url": "https://real.example.net", "target_uid": "",
                 "api_paths": {}, "kind": "generic"},
        "auth": {}, "cookies": {}, "network": {}, "output": {}, "safety": {}
    })
    with pytest.raises(ConfigError, match="placeholder"):
        load(cfg)


def test_normalize_flat_legacy_schema():
    raw = {
        "base_url": "https://site.example.net",
        "target_uid": "u123",
        "api_paths": {"api_profile": "/p", "api_articles": "/a", "article_page": "/ap", "qa_page": "/q"},
        "auth": {"mode": "browser_auto"},
        "cookies": {},
        "save_dir": "./out",
        "qa_save_dir": "./qa/out",
        "proxy": None,
        "delay_between_articles": 2,
        "delay_between_pages": 1,
    }
    cfg = _normalize(raw)
    assert cfg["base_url"] == "https://site.example.net"
    assert cfg["target_uid"] == "u123"


def test_normalize_nested_schema():
    raw = {
        "site": {
            "kind": "generic",
            "base_url": "https://site.example.net",
            "target_uid": "u456",
            "api_paths": {"profile": "/p", "articles": "/a", "article_page": "/ap", "qa_page": "/q"},
        },
        "auth": {"mode": "browser_auto"},
        "network": {"proxy": None, "delay_between_pages": 1, "delay_between_items": 2},
        "output": {"root_dir": "./output", "qa_dir": "./qa/output"},
        "safety": {},
    }
    cfg = _normalize(raw)
    assert cfg["base_url"] == "https://site.example.net"
    assert cfg["target_uid"] == "u456"
    assert cfg["site_kind"] == "generic"
