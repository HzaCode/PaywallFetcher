"""Authentication layer.

Priority order for credential resolution:
  1. env_token        — PAYWALLFETCHER_TOKEN env var (cookie string or bearer token)
  2. env_cookie_header — PAYWALLFETCHER_COOKIE_<NAME> env vars (individual cookies)
  3. browser_auto     — local Chrome / Edge logged-in session
  4. config_cookies   — cookies field in config.json (debug-only fallback)

resolve() never prints. All warnings are stored in config['_warnings'] and
emitted by the caller (cli.py) according to output mode.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from .errors import AuthError

try:
    import browser_cookie3
    _HAS_BROWSER_COOKIE3 = True
except ImportError:
    browser_cookie3 = None  # type: ignore[assignment]
    _HAS_BROWSER_COOKIE3 = False

_DEFAULT_BROWSER_ORDER = ("chrome", "edge")
_DEFAULT_XSRF_NAMES = ("XSRF-TOKEN", "XSRF_TOKEN", "xsrf-token", "x-xsrf-token", "_xsrf")

ENV_TOKEN_VAR = "PAYWALLFETCHER_TOKEN"
ENV_COOKIE_PREFIX = "PAYWALLFETCHER_COOKIE_"


def resolve(config: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve auth. Never prints. Warnings are stored in config['_warnings'].

    Injects into config:
      _auth_source, _cookie_records, _cookies, _xsrf_token, _warnings
    """
    warnings: List[str] = []
    auth = config.get("auth", {})
    mode = (auth.get("mode") or "browser_auto").lower()

    cookie_domains = auth.get("cookie_domains") or _derive_domains(config["base_url"])
    xsrf_names = auth.get("xsrf_cookie_names") or list(_DEFAULT_XSRF_NAMES)
    required = auth.get("required_cookies") or []

    # ── Priority 1: env_token ──────────────────────────────────────────────
    records = _env_token_records(config)
    if records:
        config["_auth_source"] = "env_token"
    else:
        # ── Priority 2: env_cookie_header ──────────────────────────────────
        records = _env_cookie_records(config)
        if records:
            config["_auth_source"] = "env_cookie_header"
        else:
            # ── Priority 3: browser_auto ───────────────────────────────────
            manual = _manual_records(config)
            browser_records: List[Dict] = []
            browser_name: Optional[str] = None
            browser_errors: List[str] = []

            if mode in {"browser", "browser_auto"}:
                browser_records, browser_name, browser_errors = _load_browser_records(
                    auth.get("browser", "auto"), cookie_domains
                )

            if browser_records:
                records = _merge(manual, browser_records)
                config["_auth_source"] = f"browser:{browser_name}"
            elif manual:
                # ── Priority 4: config_cookies (debug-only) ────────────────
                records = manual
                config["_auth_source"] = "config_cookies"
                if mode in {"browser", "browser_auto"} and browser_errors:
                    warnings.append(
                        f"Browser auth unavailable, falling back to config cookies "
                        f"(debug-only): {' | '.join(browser_errors)}"
                    )
            elif mode == "config":
                raise AuthError("No cookies found in config.json under 'cookies'.")
            else:
                detail = " | ".join(browser_errors) if browser_errors else "No matching cookies in local browser profiles."
                raise AuthError(
                    f"Failed to load browser cookies automatically. {detail}\n"
                    "  Ensure you are already logged into the target site in Chrome or Edge.\n"
                    f"  Alternatively, set {ENV_TOKEN_VAR} or {ENV_COOKIE_PREFIX}<NAME> env vars."
                )

    cookies_dict = {r["name"]: r["value"] for r in records}
    xsrf = _find_xsrf(cookies_dict, xsrf_names)

    missing = [n for n in required if n not in cookies_dict]
    if missing and config.get("_auth_source", "").startswith("browser"):
        warnings.append(
            f"Browser auth loaded but missing required cookies: {', '.join(missing)}"
        )

    config["_cookie_records"] = records
    config["_cookies"] = cookies_dict
    config["_xsrf_token"] = xsrf
    config["_warnings"] = warnings
    return config


def create_session(config: Dict[str, Any]) -> requests.Session:
    """Build a requests.Session with cookies, headers, and optional proxy."""
    session = requests.Session()

    for rec in config.get("_cookie_records", []):
        session.cookies.set(
            rec["name"], rec["value"],
            domain=rec.get("domain") or None,
            path=rec.get("path") or "/",
        )

    if not config.get("_cookie_records"):
        session.cookies.update(config.get("_cookies", {}))

    base_url = config["base_url"]
    referer = f"{base_url}/u/{config['target_uid']}" if config.get("target_uid") else base_url
    session.headers.update({
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "referer": referer,
        "accept": "application/json, text/plain, */*",
    })

    if config.get("_xsrf_token"):
        session.headers["x-xsrf-token"] = config["_xsrf_token"]

    proxy = config.get("proxy")
    if proxy:
        session.proxies.update({"http": proxy, "https": proxy})

    return session


def build_playwright_cookies(config: Dict[str, Any]) -> List[Dict]:
    """Build a Playwright-compatible cookie list from resolved records."""
    seen: set = set()
    result = []
    for rec in config.get("_cookie_records", []):
        domain = rec.get("domain")
        if not domain:
            continue
        key = (rec["name"], domain, rec.get("path") or "/")
        if key in seen:
            continue
        seen.add(key)
        entry: Dict = {
            "name": rec["name"],
            "value": rec["value"],
            "domain": domain,
            "path": rec.get("path") or "/",
            "secure": bool(rec.get("secure", False)),
        }
        # Preserve optional Playwright-supported fields
        for field in ("httpOnly", "sameSite"):
            if field in rec:
                entry[field] = rec[field]
        expires = rec.get("expires")
        if isinstance(expires, (int, float)) and expires > 0:
            entry["expires"] = float(expires)
        result.append(entry)
    return result


def redact_proxy(url: Optional[str]) -> str:
    """Remove credentials from a proxy URL before logging."""
    if not url:
        return "none"
    return re.sub(r"(https?://)[^@]+@", r"\1***@", url)


def doctor_auth(config: Dict[str, Any]) -> Dict[str, Any]:
    """Return a structured auth health check (does not raise)."""
    result: Dict[str, Any] = {
        "ok": False,
        "auth_source": config.get("_auth_source", "unknown"),
        "cookie_count": len(config.get("_cookie_records", [])),
        "required_cookies_missing": [],
        "xsrf_found": bool(config.get("_xsrf_token")),
    }
    required = config.get("auth", {}).get("required_cookies") or []
    cookies_dict = config.get("_cookies", {})
    result["required_cookies_missing"] = [n for n in required if n not in cookies_dict]
    result["ok"] = not result["required_cookies_missing"]
    return result


# ── env credential helpers ─────────────────────────────────────────────────


def _env_token_records(config: Dict[str, Any]) -> List[Dict]:
    """Parse PAYWALLFETCHER_TOKEN env var into cookie records.

    Accepts a semicolon-separated cookie string: ``SESSION=abc; XSRF-TOKEN=xyz``
    Each ``NAME=value`` pair becomes one cookie record bound to the config host.
    Returns an empty list if the env var is unset or empty.
    """
    token = os.environ.get(ENV_TOKEN_VAR, "").strip()
    if not token:
        return []

    host = _normalize_domain(urlparse(config["base_url"]).netloc.split(":")[0])
    domain = f".{host}" if host else None

    records: List[Dict] = []
    for part in token.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        name = name.strip()
        value = value.strip()
        if name:
            records.append({
                "name": name, "value": value,
                "domain": domain, "path": "/",
                "secure": True, "expires": None,
            })
    return records


def _env_cookie_records(config: Dict[str, Any]) -> List[Dict]:
    """Collect PAYWALLFETCHER_COOKIE_<NAME>=value env vars as cookie records.

    Each env var whose name starts with ``PAYWALLFETCHER_COOKIE_`` contributes
    one cookie; the cookie name is the suffix after the prefix.
    Returns an empty list if no matching env vars are set.
    """
    host = _normalize_domain(urlparse(config["base_url"]).netloc.split(":")[0])
    domain = f".{host}" if host else None

    records: List[Dict] = []
    for key, value in os.environ.items():
        if not key.startswith(ENV_COOKIE_PREFIX):
            continue
        name = key[len(ENV_COOKIE_PREFIX):]
        value = value.strip()
        if name and value:
            records.append({
                "name": name, "value": value,
                "domain": domain, "path": "/",
                "secure": True, "expires": None,
            })
    return records


# ── internals ──────────────────────────────────────────────────────────────


def _load_browser_records(
    browser_pref: str, domains: List[str]
) -> Tuple[List[Dict], Optional[str], List[str]]:
    if not _HAS_BROWSER_COOKIE3:
        return [], None, ["browser-cookie3 is not installed (pip install browser-cookie3)"]

    order = list(_DEFAULT_BROWSER_ORDER) if browser_pref in ("", "auto") else [browser_pref]
    errors: List[str] = []

    for candidate in order:
        loader = getattr(browser_cookie3, candidate, None)
        if loader is None:
            errors.append(f"unsupported browser '{candidate}'")
            continue
        records, errs = _collect_records(loader, domains)
        errors.extend(errs)
        if records:
            return records, candidate, errors

    return [], None, errors


def _collect_records(loader: Any, domains: List[str]) -> Tuple[List[Dict], List[str]]:
    seen: set = set()
    records: List[Dict] = []
    errors: List[str] = []
    for domain in domains:
        try:
            jar = loader(domain_name=domain)
        except Exception as exc:
            errors.append(f"{domain}: {exc}")
            continue
        for cookie in jar:
            if not _domain_matches(cookie.domain, domains):
                continue
            rec = _cookie_to_record(cookie)
            key = (rec["name"], rec["domain"], rec["path"])
            if key in seen:
                continue
            seen.add(key)
            records.append(rec)
    return records, errors


def _cookie_to_record(cookie: Any) -> Dict:
    expires = getattr(cookie, "expires", None)
    if expires == 0:
        expires = None
    return {
        "name": cookie.name,
        "value": cookie.value,
        "domain": cookie.domain,
        "path": cookie.path or "/",
        "secure": bool(cookie.secure),
        "expires": expires,
        "httpOnly": bool(getattr(cookie, "has_nonstandard_attr", lambda _: False)("HttpOnly")),
    }


def _manual_records(config: Dict[str, Any]) -> List[Dict]:
    cookies = {k: v for k, v in (config.get("cookies") or {}).items() if v}
    if not cookies:
        return []
    host = _normalize_domain(urlparse(config["base_url"]).netloc.split(":")[0])
    domain = f".{host}" if host else None
    return [
        {"name": n, "value": v, "domain": domain, "path": "/", "secure": True, "expires": None}
        for n, v in cookies.items()
    ]


def _merge(primary: List[Dict], secondary: List[Dict]) -> List[Dict]:
    merged: List[Dict] = []
    index: Dict = {}
    for rec in primary + secondary:
        key = (rec["name"], rec.get("domain"), rec.get("path") or "/")
        if key in index:
            merged[index[key]] = rec
        else:
            index[key] = len(merged)
            merged.append(rec)
    return merged


def _find_xsrf(cookies: Dict[str, str], names: List[str]) -> str:
    lowered = {k.lower(): v for k, v in cookies.items()}
    for name in names:
        val = cookies.get(name) or lowered.get(name.lower())
        if val:
            return val
    return ""


def _derive_domains(base_url: str) -> List[str]:
    host = _normalize_domain(urlparse(base_url).netloc.split(":")[0])
    result = []
    seen: set = set()
    for candidate in _candidate_domains(host):
        if candidate and candidate not in seen:
            seen.add(candidate)
            result.append(candidate)
    return result


def _candidate_domains(host: str) -> List[str]:
    if not host:
        return []
    candidates = [host]
    if host.startswith("www."):
        candidates.append(host[4:])
    parts = host.split(".")
    if len(parts) >= 2:
        candidates.append(".".join(parts[-2:]))
    return candidates


def _domain_matches(cookie_domain: str, domains: List[str]) -> bool:
    nd = _normalize_domain(cookie_domain)
    for domain in domains:
        n = _normalize_domain(domain)
        if nd == n or nd.endswith(f".{n}") or n.endswith(f".{nd}"):
            return True
    return False


def _normalize_domain(domain: str) -> str:
    return (domain or "").strip().lstrip(".").lower()
