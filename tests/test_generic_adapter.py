"""Tests for the generic site adapter."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
FIXTURES = ROOT / "tests" / "fixtures"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paywallfetcher.sites.generic import GenericAdapter

ADAPTER = GenericAdapter()

_BASE_CONFIG = {
    "base_url": "https://site.example.net",
    "target_uid": "u123",
    "api_paths": {
        "api_profile": "/ajax/profile/info?uid={uid}",
        "api_articles": "/ajax/statuses/articles?uid={uid}&page={page}&feature=10",
        "article_page": "/article/p/show?id={article_id}",
        "qa_page": "/p/{qa_id}",
    },
}


def _load_fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_adapter_key():
    assert ADAPTER.key == "generic"


def test_parse_article_list():
    payload = _load_fixture("article_list_payload.json")
    refs = ADAPTER.parse_article_list(payload, _BASE_CONFIG)
    assert len(refs) == 2
    assert refs[0].article_id == "article_abc123"
    assert refs[0].title == "Test Article Title"
    assert refs[1].article_id == "article_def456"


def test_parse_article_list_skips_non_articles():
    payload = {"data": {"list": [
        {"id": "p1", "page_info": {"object_type": "video", "page_id": "v001"}, "user": {}}
    ]}}
    refs = ADAPTER.parse_article_list(payload, _BASE_CONFIG)
    assert refs == []


def test_parse_qa_list():
    payload = _load_fixture("qa_list_payload.json")
    refs = ADAPTER.parse_qa_list(payload)
    assert len(refs) == 1
    assert refs[0].id == "qa_xyz789"
    assert "meaning of life" in refs[0].question


def test_build_article_list_url():
    url = ADAPTER.build_article_list_url(_BASE_CONFIG, page=3)
    assert "page=3" in url
    assert "u123" in url


def test_build_qa_url():
    url = ADAPTER.build_qa_url(_BASE_CONFIG, "qa_xyz789")
    assert "qa_xyz789" in url


def test_unlock_selectors_not_empty():
    sel = ADAPTER.unlock_selectors()
    assert sel.trigger
    assert len(sel.answer) > 0
    assert len(sel.question) > 0
