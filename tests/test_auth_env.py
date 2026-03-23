"""Tests for env-based credential resolution (env_token / env_cookie_header priority)."""

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from paywallfetcher.auth import (
    ENV_COOKIE_PREFIX,
    ENV_TOKEN_VAR,
    _env_cookie_records,
    _env_token_records,
    resolve,
)


_BASE_CFG = {
    "base_url": "https://site.example.net",
    "target_uid": "123456",
    "auth": {"mode": "browser_auto", "required_cookies": ["SESSION"]},
    "cookies": {},
}


def _cfg():
    import copy
    return copy.deepcopy(_BASE_CFG)


# ── env_token source ───────────────────────────────────────────────────────

def test_env_token_parses_cookie_string(monkeypatch):
    """PAYWALLFETCHER_TOKEN=NAME=val; NAME2=val2 should yield two cookie records."""
    monkeypatch.setenv(ENV_TOKEN_VAR, "SESSION=abc123; XSRF-TOKEN=xyz")
    records = _env_token_records(_cfg())
    assert len(records) == 2
    names = {r["name"] for r in records}
    assert "SESSION" in names
    assert "XSRF-TOKEN" in names


def test_env_token_empty_returns_empty(monkeypatch):
    monkeypatch.delenv(ENV_TOKEN_VAR, raising=False)
    assert _env_token_records(_cfg()) == []


def test_env_token_blank_value_returns_empty(monkeypatch):
    monkeypatch.setenv(ENV_TOKEN_VAR, "   ")
    assert _env_token_records(_cfg()) == []


def test_env_token_domain_bound_to_config_host(monkeypatch):
    monkeypatch.setenv(ENV_TOKEN_VAR, "SESSION=abc")
    records = _env_token_records(_cfg())
    assert records[0]["domain"] == ".site.example.net"


def test_env_token_priority_over_browser(monkeypatch):
    """env_token must win even when browser_auto is the configured mode."""
    monkeypatch.setenv(ENV_TOKEN_VAR, "SESSION=env_value; XSRF-TOKEN=tok")
    cfg = _cfg()
    resolved = resolve(cfg)
    assert resolved["_auth_source"] == "env_token"
    assert resolved["_cookies"]["SESSION"] == "env_value"


# ── env_cookie_header source ───────────────────────────────────────────────

def test_env_cookie_prefix_collects_records(monkeypatch):
    monkeypatch.setenv(f"{ENV_COOKIE_PREFIX}SESSION", "sess_val")
    monkeypatch.setenv(f"{ENV_COOKIE_PREFIX}MYTOKEN", "tok_val")
    records = _env_cookie_records(_cfg())
    names = {r["name"]: r["value"] for r in records}
    assert names.get("SESSION") == "sess_val"
    assert names.get("MYTOKEN") == "tok_val"


def test_env_cookie_prefix_empty_value_ignored(monkeypatch):
    monkeypatch.setenv(f"{ENV_COOKIE_PREFIX}SESSION", "   ")
    records = _env_cookie_records(_cfg())
    assert records == []


def test_env_cookie_priority_over_browser_when_no_env_token(monkeypatch):
    """env_cookie_header wins over browser when PAYWALLFETCHER_TOKEN is absent."""
    monkeypatch.delenv(ENV_TOKEN_VAR, raising=False)
    monkeypatch.setenv(f"{ENV_COOKIE_PREFIX}SESSION", "env_cookie_val")
    cfg = _cfg()
    resolved = resolve(cfg)
    assert resolved["_auth_source"] == "env_cookie_header"
    assert resolved["_cookies"]["SESSION"] == "env_cookie_val"


def test_env_token_beats_env_cookie(monkeypatch):
    """env_token (priority 1) must win over env_cookie_header (priority 2)."""
    monkeypatch.setenv(ENV_TOKEN_VAR, "SESSION=token_wins")
    monkeypatch.setenv(f"{ENV_COOKIE_PREFIX}SESSION", "cookie_loses")
    cfg = _cfg()
    resolved = resolve(cfg)
    assert resolved["_auth_source"] == "env_token"
    assert resolved["_cookies"]["SESSION"] == "token_wins"


# ── resolve() never prints ─────────────────────────────────────────────────

def test_resolve_does_not_print_to_stdout(monkeypatch, capsys):
    """resolve() must never write to stdout regardless of auth outcome."""
    monkeypatch.setenv(ENV_TOKEN_VAR, "SESSION=s; XSRF-TOKEN=x")
    resolve(_cfg())
    captured = capsys.readouterr()
    assert captured.out == ""


def test_resolve_does_not_print_to_stderr(monkeypatch, capsys):
    """resolve() must not print to stderr — warnings go into _warnings list."""
    monkeypatch.setenv(ENV_TOKEN_VAR, "SESSION=s; XSRF-TOKEN=x")
    resolve(_cfg())
    captured = capsys.readouterr()
    assert captured.err == ""


def test_resolve_stores_warnings_in_config(monkeypatch):
    """Warnings must be in config['_warnings'], not printed."""
    monkeypatch.delenv(ENV_TOKEN_VAR, raising=False)
    for k in list(os.environ):
        if k.startswith(ENV_COOKIE_PREFIX):
            monkeypatch.delenv(k)

    cfg = _cfg()
    cfg["cookies"] = {"SESSION": "manual_val"}
    cfg["auth"]["mode"] = "browser_auto"

    resolved = resolve(cfg)
    assert "_warnings" in resolved
    assert isinstance(resolved["_warnings"], list)


# ── redaction: token must not appear in summaries ──────────────────────────

def test_token_value_not_in_json_summary(monkeypatch, capsys):
    """The token value must not appear in --json CLI output."""
    import json as json_mod
    from paywallfetcher.cli import run

    secret = "SECRET_SESSION_VALUE_ABC123"
    monkeypatch.setenv(ENV_TOKEN_VAR, f"SESSION={secret}; XSRF-TOKEN=xsrf_val")

    cfg_data = {
        "site": {
            "base_url": "https://site.example.net",
            "target_uid": "123456",
            "api_paths": {},
            "kind": "generic",
        },
        "auth": {"mode": "browser_auto", "required_cookies": ["SESSION"]},
        "network": {},
        "output": {},
        "safety": {},
    }

    import tempfile, os as _os
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json_mod.dump(cfg_data, f)
        cfg_path = f.name

    try:
        run(["--json", "--config", cfg_path, "auth", "check"])
        captured = capsys.readouterr()
        assert secret not in captured.out, "Secret must not appear in JSON output"
        assert secret not in captured.err, "Secret must not appear in stderr"
    finally:
        _os.unlink(cfg_path)


def test_proxy_credentials_redacted(monkeypatch, capsys):
    """Proxy passwords must not appear in any output."""
    from paywallfetcher.auth import redact_proxy

    redacted = redact_proxy("http://user:SECRETPASS@proxy.example.com:8080")
    assert "SECRETPASS" not in redacted
    assert "***" in redacted
