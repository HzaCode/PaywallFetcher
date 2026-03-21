"""Configuration loading and validation.

Supports both the new nested schema (site/auth/network/output/safety)
and the legacy flat schema for backward compatibility.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from .errors import ConfigError

_PLACEHOLDERS = {"YOUR_TARGET_UID", "YOUR_UID", "CHANGE_ME", "YOUR_ID_HERE", ""}
_DEFAULT_CONFIG_FILE = "config.json"


def load(config_file: str = _DEFAULT_CONFIG_FILE, required_api_paths: tuple = ()) -> Dict[str, Any]:
    """Load, validate, and normalise config.json.

    Raises ConfigError for any validation failure so the caller can map it to
    the correct exit code without calling sys.exit() inside a library function.
    """
    if not os.path.exists(config_file):
        raise ConfigError(
            f"{config_file} not found. Copy config.example.json to config.json and fill in your settings."
        )

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"config.json is not valid JSON: {exc}") from exc

    config = _normalize(raw)
    _validate(config, required_api_paths)
    return config


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Accept both new (nested) and legacy (flat) schema; always return flat internal form."""
    config: Dict[str, Any] = {}

    site = raw.get("site") or {}
    config["base_url"] = (site.get("base_url") or raw.get("base_url") or "").strip().rstrip("/")
    config["target_uid"] = str(site.get("target_uid") or raw.get("target_uid") or "").strip()

    raw_paths = site.get("api_paths") or raw.get("api_paths") or {}
    config["api_paths"] = {
        "api_profile": raw_paths.get("profile") or raw_paths.get("api_profile") or "",
        "api_articles": raw_paths.get("articles") or raw_paths.get("api_articles") or "",
        "article_page": raw_paths.get("article_page") or "",
        "qa_page": raw_paths.get("qa_page") or "",
    }

    config["site_kind"] = site.get("kind") or raw.get("site_kind") or "generic"

    auth = dict(raw.get("auth") or {})
    auth.setdefault("mode", "browser_auto")
    auth.setdefault("browser", "auto")
    auth.setdefault("cookie_domains", [])
    auth.setdefault("required_cookies", [])
    auth.setdefault("xsrf_cookie_names", ["XSRF-TOKEN", "XSRF_TOKEN", "xsrf-token", "_xsrf"])
    config["auth"] = auth

    config["cookies"] = dict(raw.get("cookies") or {})

    net = dict(raw.get("network") or {})
    config["proxy"] = net.get("proxy") or raw.get("proxy")
    config["delay_between_articles"] = net.get("delay_between_items") or raw.get("delay_between_articles") or 2
    config["delay_between_pages"] = net.get("delay_between_pages") or raw.get("delay_between_pages") or 1
    config["request_timeout"] = net.get("request_timeout") or 20
    config["max_retries"] = net.get("max_retries") or 3

    out = dict(raw.get("output") or {})
    config["save_dir"] = out.get("root_dir") or raw.get("save_dir") or "./output"
    config["qa_save_dir"] = out.get("qa_dir") or raw.get("qa_save_dir") or "./qa/output"
    config["download_images"] = out.get("download_images") if "download_images" in out else True
    config["save_html"] = out.get("save_html") if "save_html" in out else True
    config["save_text"] = out.get("save_text") if "save_text" in out else True

    safety = dict(raw.get("safety") or {})
    config["allowed_base_domains"] = safety.get("allowed_base_domains") or []

    return config


def _validate(config: Dict[str, Any], required_api_paths: tuple) -> None:
    base_url = config["base_url"]
    if not base_url or "example.com" in base_url:
        raise ConfigError("'base_url' must be set to the real target site URL (not example.com).")

    if config["allowed_base_domains"]:
        from urllib.parse import urlparse
        host = urlparse(base_url).hostname or ""
        if not any(host == d or host.endswith("." + d) for d in config["allowed_base_domains"]):
            raise ConfigError(
                f"base_url host '{host}' is not in allowed_base_domains: {config['allowed_base_domains']}"
            )

    uid = config["target_uid"]
    if uid in _PLACEHOLDERS:
        raise ConfigError("'target_uid' is still a placeholder. Set it to the real target user ID.")

    for key in required_api_paths:
        if not config["api_paths"].get(key):
            raise ConfigError(f"api_paths.{key} is required but not set.")
