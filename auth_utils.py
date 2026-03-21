import json
import os
from urllib.parse import urlparse

import requests

try:
    import browser_cookie3
except ImportError:
    browser_cookie3 = None


DEFAULT_BROWSER_ORDER = ("chrome", "edge")
DEFAULT_REQUIRED_COOKIES = ()
DEFAULT_XSRF_COOKIE_NAMES = (
    "XSRF-TOKEN",
    "XSRF_TOKEN",
    "xsrf-token",
    "x-xsrf-token",
    "_xsrf",
)


def load_config(config_file, required_api_paths=(), require_target_uid=True):
    if not os.path.exists(config_file):
        print(f"[Error] {config_file} not found.")
        print("  Please copy config.example.json to config.json and fill in your settings.")
        raise SystemExit(1)

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    base_url = (config.get("base_url") or "").strip()
    if not base_url or "example.com" in base_url:
        print("[Error] 'base_url' must be set to the real target site URL.")
        raise SystemExit(1)
    config["base_url"] = base_url.rstrip("/")

    if require_target_uid and not config.get("target_uid"):
        print("[Error] 'target_uid' is required.")
        raise SystemExit(1)

    for key in required_api_paths:
        if not config.get("api_paths", {}).get(key):
            print(f"[Error] 'api_paths.{key}' is required.")
            raise SystemExit(1)

    auth = dict(config.get("auth") or {})
    auth["mode"] = (auth.get("mode") or "browser_auto").lower()
    auth["browser"] = (auth.get("browser") or "auto").lower()
    auth["cookie_domains"] = normalize_domains(auth.get("cookie_domains") or derive_cookie_domains(config["base_url"]))
    auth["required_cookies"] = [item for item in auth.get("required_cookies") or DEFAULT_REQUIRED_COOKIES]
    auth["xsrf_cookie_names"] = [item for item in auth.get("xsrf_cookie_names") or DEFAULT_XSRF_COOKIE_NAMES]
    config["auth"] = auth

    config["_cookie_records"] = resolve_cookie_records(config)
    config["_cookies"] = records_to_cookie_dict(config["_cookie_records"])
    config["_xsrf_token"] = find_xsrf_token(config["_cookies"], auth["xsrf_cookie_names"])

    missing = [name for name in auth["required_cookies"] if name not in config["_cookies"]]
    if auth["mode"] in {"browser", "browser_auto"} and missing and config.get("_auth_source", "").startswith("browser"):
        print(f"[Warn] Browser auth loaded but missing cookies: {', '.join(missing)}")

    return config


def create_session(config):
    session = requests.Session()
    for cookie in config.get("_cookie_records", []):
        session.cookies.set(
            cookie["name"],
            cookie["value"],
            domain=cookie.get("domain") or None,
            path=cookie.get("path") or "/",
        )

    if not config.get("_cookie_records"):
        session.cookies.update(config.get("_cookies", {}))

    base_url = config["base_url"]
    referer = base_url
    if config.get("target_uid"):
        referer = f"{base_url}/u/{config['target_uid']}"

    session.headers.update(
        {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
            ),
            "referer": referer,
            "accept": "application/json, text/plain, */*",
        }
    )

    if config.get("_xsrf_token"):
        session.headers["x-xsrf-token"] = config["_xsrf_token"]

    proxy = config.get("proxy")
    if proxy:
        session.proxies.update({"http": proxy, "https": proxy})

    return session


def build_playwright_cookies(config):
    cookies = []
    seen = set()
    for cookie in config.get("_cookie_records", []):
        domain = cookie.get("domain")
        if not domain:
            continue
        key = (cookie["name"], domain, cookie.get("path") or "/")
        if key in seen:
            continue
        seen.add(key)
        item = {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": domain,
            "path": cookie.get("path") or "/",
            "secure": bool(cookie.get("secure", False)),
        }
        expires = cookie.get("expires")
        if isinstance(expires, (int, float)) and expires > 0:
            item["expires"] = float(expires)
        cookies.append(item)
    return cookies


def resolve_cookie_records(config):
    auth = config.get("auth", {})
    mode = auth.get("mode", "browser_auto")
    manual_records = manual_cookie_records(config)
    browser_records = []
    browser_name = None
    browser_errors = []

    if mode in {"browser", "browser_auto"}:
        browser_records, browser_name, browser_errors = load_browser_cookie_records(
            auth.get("browser", "auto"),
            auth.get("cookie_domains") or derive_cookie_domains(config["base_url"]),
        )

    if browser_records:
        config["_auth_source"] = f"browser:{browser_name}"
        return merge_cookie_records(manual_records, browser_records)

    if manual_records:
        config["_auth_source"] = "config"
        if mode in {"browser", "browser_auto"} and browser_errors:
            print(f"[Warn] Browser auth unavailable, falling back to config cookies: {' | '.join(browser_errors)}")
        return manual_records

    if mode == "config":
        print("[Error] No cookies found in config.json.")
        raise SystemExit(1)

    detail = " | ".join(browser_errors) if browser_errors else "No matching cookies found in local browser profiles."
    print(f"[Error] Failed to load browser cookies automatically. {detail}")
    print("  Please make sure you are already logged into the target site in Chrome or Edge.")
    raise SystemExit(1)


def load_browser_cookie_records(browser_name, domains):
    if browser_cookie3 is None:
        return [], None, ["browser-cookie3 is not installed"]

    browser_order = list(DEFAULT_BROWSER_ORDER) if browser_name in {"", "auto", None} else [browser_name]
    errors = []

    for candidate in browser_order:
        loader = getattr(browser_cookie3, candidate, None)
        if loader is None:
            errors.append(f"unsupported browser '{candidate}'")
            continue

        records = []
        seen = set()
        for domain in domains:
            try:
                jar = loader(domain_name=domain)
            except Exception as exc:
                errors.append(f"{candidate}:{domain}:{exc}")
                continue

            for cookie in jar:
                if not domain_matches(cookie.domain, domains):
                    continue
                record = cookie_to_record(cookie)
                key = (record["name"], record["domain"], record["path"])
                if key in seen:
                    continue
                seen.add(key)
                records.append(record)

        if records:
            return records, candidate, errors

    return [], None, errors


def manual_cookie_records(config):
    cookies = {k: v for k, v in (config.get("cookies") or {}).items() if v}
    if not cookies:
        return []

    host = normalize_domain(urlparse(config["base_url"]).netloc.split(":")[0])
    domain = f".{host}" if host else None
    records = []
    for name, value in cookies.items():
        records.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "secure": True,
                "expires": None,
            }
        )
    return records


def merge_cookie_records(primary_records, secondary_records):
    merged = []
    index = {}
    for record in primary_records + secondary_records:
        key = (record["name"], record.get("domain"), record.get("path") or "/")
        if key in index:
            merged[index[key]] = record
        else:
            index[key] = len(merged)
            merged.append(record)
    return merged


def cookie_to_record(cookie):
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
    }


def records_to_cookie_dict(records):
    cookies = {}
    for record in records:
        cookies[record["name"]] = record["value"]
    return cookies


def find_xsrf_token(cookies, xsrf_cookie_names):
    lowered = {name.lower(): value for name, value in cookies.items()}
    for name in xsrf_cookie_names:
        value = cookies.get(name)
        if value:
            return value
        value = lowered.get(name.lower())
        if value:
            return value
    return ""


def normalize_domains(domains):
    result = []
    seen = set()
    for domain in domains:
        normalized = normalize_domain(domain)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def derive_cookie_domains(base_url):
    host = normalize_domain(urlparse(base_url).netloc.split(":")[0])
    domains = []
    if host:
        domains.append(host)
        if host.startswith("www."):
            domains.append(host[4:])
        parts = host.split(".")
        if len(parts) >= 2:
            domains.append(".".join(parts[-2:]))

    return normalize_domains(domains)


def domain_matches(cookie_domain, domains):
    normalized_cookie_domain = normalize_domain(cookie_domain)
    for domain in domains:
        normalized = normalize_domain(domain)
        if (
            normalized_cookie_domain == normalized
            or normalized_cookie_domain.endswith(f".{normalized}")
            or normalized.endswith(f".{normalized_cookie_domain}")
        ):
            return True
    return False


def normalize_domain(domain):
    return (domain or "").strip().lstrip(".").lower()
