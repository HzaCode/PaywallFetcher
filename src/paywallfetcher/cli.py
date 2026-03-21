"""Unified CLI for PaywallFetcher.

Usage:
    py -m paywallfetcher article list
    py -m paywallfetcher article fetch [--new-only] [--start N] [--no-images] [--json]
    py -m paywallfetcher qa list
    py -m paywallfetcher qa fetch [--new-only] [--start N] [--json]
    py -m paywallfetcher qa browser-fetch [--batch-size N] [--headless] [--json]
    py -m paywallfetcher auth check [--json]
    py -m paywallfetcher doctor [--json]
    py -m paywallfetcher state inspect [--json]
    py -m paywallfetcher state reset
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional

from . import __version__
from .errors import PaywallFetcherError

# ── top-level parser ───────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paywallfetcher",
        description="PaywallFetcher — authorized content retrieval skill for OpenClaw.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"paywallfetcher {__version__}")
    parser.add_argument(
        "--config", default="config.json", metavar="FILE",
        help="Path to config.json (default: config.json)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON output instead of human-readable text",
    )

    sub = parser.add_subparsers(dest="group", metavar="COMMAND")

    _add_article_commands(sub)
    _add_qa_commands(sub)
    _add_auth_commands(sub)
    _add_doctor_command(sub)
    _add_state_commands(sub)

    return parser


def _add_article_commands(sub: Any) -> None:
    g = sub.add_parser("article", help="Article commands")
    gs = g.add_subparsers(dest="action", metavar="ACTION")

    ls = gs.add_parser("list", help="List articles without downloading")
    ls.add_argument("--max-pages", type=int, default=200)

    fetch = gs.add_parser("fetch", help="Download articles")
    fetch.add_argument("--new-only", action="store_true", help="Incremental mode")
    fetch.add_argument("--start", type=int, default=1, help="Start from Nth article (1-based)")
    fetch.add_argument("--no-images", action="store_true", help="Skip image downloads")
    fetch.add_argument("--max-pages", type=int, default=200)
    fetch.add_argument("--dry-run", action="store_true", help="List what would be downloaded without saving")
    fetch.add_argument("--fail-on-empty", action="store_true", help="Exit 10 if no new content in incremental mode")


def _add_qa_commands(sub: Any) -> None:
    g = sub.add_parser("qa", help="Q&A commands")
    gs = g.add_subparsers(dest="action", metavar="ACTION")

    ls = gs.add_parser("list", help="List Q&A without downloading")
    ls.add_argument("--max-pages", type=int, default=200)

    fetch = gs.add_parser("fetch", help="Download Q&A via requests")
    fetch.add_argument("--new-only", action="store_true")
    fetch.add_argument("--start", type=int, default=1)
    fetch.add_argument("--max-pages", type=int, default=200)
    fetch.add_argument("--fail-on-empty", action="store_true")

    bf = gs.add_parser("browser-fetch", help="Retrieve Q&A via authorized browser session")
    bf.add_argument("--batch-size", type=int, default=5)
    bf.add_argument("--headless", action="store_true",
                    help="Run in headless mode (default: headed for first-run/debug)")
    bf.add_argument("--no-screenshots", action="store_true", help="Disable failure screenshots")


def _add_auth_commands(sub: Any) -> None:
    g = sub.add_parser("auth", help="Authentication commands")
    gs = g.add_subparsers(dest="action", metavar="ACTION")
    gs.add_parser("check", help="Verify browser session cookies are available")


def _add_doctor_command(sub: Any) -> None:
    sub.add_parser("doctor", help="Run full pre-flight diagnostic check")


def _add_state_commands(sub: Any) -> None:
    g = sub.add_parser("state", help="State file commands")
    gs = g.add_subparsers(dest="action", metavar="ACTION")
    gs.add_parser("inspect", help="Show current download state")
    gs.add_parser("reset", help="Delete state file to force full re-scan")


# ── dispatch ───────────────────────────────────────────────────────────────

def run(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.group is None:
        parser.print_help()
        return 0

    emit_json = getattr(args, "json", False)

    try:
        return _dispatch(args, emit_json)
    except PaywallFetcherError as exc:
        if emit_json:
            print(json.dumps({"ok": False, "error": str(exc), "exit_code": exc.exit_code}))
        else:
            print(f"[{type(exc).__name__}] {exc}")
        return exc.exit_code
    except KeyboardInterrupt:
        return 130


def _dispatch(args: argparse.Namespace, emit_json: bool) -> int:
    from . import auth as auth_mod
    from . import config as config_mod

    if args.group == "doctor":
        return _cmd_doctor(args, emit_json)

    if args.group == "auth":
        return _cmd_auth(args, emit_json)

    if args.group == "state":
        return _cmd_state(args, emit_json)

    cfg = config_mod.load(args.config)
    cfg = auth_mod.resolve(cfg)

    if args.group == "article":
        return _cmd_article(args, cfg, emit_json)

    if args.group == "qa":
        return _cmd_qa(args, cfg, emit_json)

    return 0


# ── article ────────────────────────────────────────────────────────────────

def _cmd_article(args: argparse.Namespace, config: Dict[str, Any], emit_json: bool) -> int:
    from . import articles as articles_mod
    from . import auth as auth_mod
    from . import state as state_mod
    from .sites import get_adapter

    adapter = get_adapter(config.get("site_kind", "generic"))
    session = auth_mod.create_session(config)
    save_dir = config["save_dir"]
    os.makedirs(save_dir, exist_ok=True)
    state_path = os.path.join(save_dir, "_state.json")

    if not emit_json:
        _print_banner(config)
        _verify_login(session, config, adapter)

    action = args.action or "list"

    state = state_mod.load(state_path)
    known_ids = state_mod.downloaded_article_ids(state) if getattr(args, "new_only", False) else None
    mode = "incremental" if known_ids is not None else "full scan"
    if not emit_json:
        print(f"\n[Fetching article list — {mode}]")

    refs, stopped_early = articles_mod.fetch_list(
        session, config, adapter,
        max_pages=getattr(args, "max_pages", 200),
        stop_at_known_ids=known_ids,
    )
    refs = articles_mod.deduplicate(refs)

    if not refs:
        msg = "No new articles since last run." if known_ids else "No articles found."
        if emit_json:
            print(json.dumps({"ok": True, "mode": mode, "listed": 0, "items": []}))
        else:
            print(f"  {msg}")
        if getattr(args, "fail_on_empty", False):
            from .errors import NoNewContentError
            raise NoNewContentError(msg)
        return 0

    _save_article_index(refs, save_dir)

    if emit_json and action == "list":
        print(json.dumps({
            "ok": True, "mode": mode, "listed": len(refs),
            "items": [{"id": r.article_id, "title": r.title, "date": r.created_at} for r in refs],
        }))
        return 0

    if not emit_json:
        print(f"\n  Found {len(refs)} articles")
        for i, r in enumerate(refs, 1):
            d = r.created_at[:16] if r.created_at else "unknown"
            print(f"    {i:3d}. [{d}] {r.title[:55]}")

    if action == "list" or getattr(args, "dry_run", False):
        if not emit_json:
            print("\n  (list-only mode)")
        return 0

    summary = articles_mod.download_all(
        session, config, adapter, refs, state, state_path, save_dir,
        start=getattr(args, "start", 1),
        no_images=getattr(args, "no_images", False),
        emit_json=emit_json,
    )

    if emit_json:
        summary["mode"] = mode
        summary["listed"] = len(refs)
        print(json.dumps(summary))
    else:
        _print_summary(summary)

    return 0


# ── qa ─────────────────────────────────────────────────────────────────────

def _cmd_qa(args: argparse.Namespace, config: Dict[str, Any], emit_json: bool) -> int:
    from . import auth as auth_mod
    from . import qa as qa_mod
    from . import state as state_mod
    from .sites import get_adapter

    adapter = get_adapter(config.get("site_kind", "generic"))
    session = auth_mod.create_session(config)
    save_dir = config["qa_save_dir"]
    os.makedirs(save_dir, exist_ok=True)
    state_path = os.path.join(save_dir, "_state.json")

    if not emit_json:
        _print_banner(config)
        _verify_login(session, config, adapter)

    action = args.action or "list"

    if action == "browser-fetch":
        return _cmd_qa_browser(args, config, adapter, save_dir, emit_json)

    state = state_mod.load(state_path)
    known_ids = state_mod.downloaded_qa_ids(state) if getattr(args, "new_only", False) else None
    mode = "incremental" if known_ids is not None else "full scan"
    if not emit_json:
        print(f"\n[Fetching Q&A list — {mode}]")

    refs, stopped_early = qa_mod.fetch_list(
        session, config, adapter,
        max_pages=getattr(args, "max_pages", 200),
        stop_at_known_ids=known_ids,
    )

    if not refs:
        msg = "No new Q&A since last run." if known_ids else "No Q&A found."
        if emit_json:
            print(json.dumps({"ok": True, "mode": mode, "listed": 0, "items": []}))
        else:
            print(f"  {msg}")
        if getattr(args, "fail_on_empty", False):
            from .errors import NoNewContentError
            raise NoNewContentError(msg)
        return 0

    _save_qa_index(refs, save_dir)

    if emit_json and action == "list":
        print(json.dumps({
            "ok": True, "mode": mode, "listed": len(refs),
            "items": [{"id": r.id, "question": r.question[:80], "date": r.date} for r in refs],
        }))
        return 0

    if not emit_json:
        print(f"\n  Found {len(refs)} Q&A items")
        for i, r in enumerate(refs, 1):
            d = r.date[:16] if r.date else "unknown"
            print(f"    {i:3d}. [{d}] {r.question[:55]}")

    if action == "list":
        if not emit_json:
            print("\n  (list-only mode)")
        return 0

    summary = qa_mod.download_all(
        session, config, adapter, refs, state, state_path, save_dir,
        start=getattr(args, "start", 1),
        emit_json=emit_json,
    )

    if emit_json:
        summary["mode"] = mode
        summary["listed"] = len(refs)
        print(json.dumps(summary))
    else:
        _print_summary(summary)

    return 0


def _cmd_qa_browser(
    args: argparse.Namespace, config: Dict[str, Any], adapter: Any,
    save_dir: str, emit_json: bool
) -> int:
    import asyncio

    from . import unlock as unlock_mod

    qa_list_file = os.path.join(save_dir, "_qa_list.json")
    if not os.path.exists(qa_list_file):
        from .errors import StateError
        raise StateError(
            f"{qa_list_file} not found. Run 'paywallfetcher qa list' first."
        )

    with open(qa_list_file, "r", encoding="utf-8") as f:
        qa_list = json.load(f)

    needs = []
    for qa in qa_list:
        qa_dir = os.path.join(save_dir, unlock_mod.qa_dir_name(qa.get("id", "")))
        if not unlock_mod.is_already_retrieved(qa_dir):
            needs.append((qa, qa_dir))

    if not needs:
        if emit_json:
            print(json.dumps({"ok": True, "total": 0, "success": 0, "failed": 0, "items": []}))
        else:
            print("  All Q&A already have full answers.")
        return 0

    if not emit_json:
        print(f"  Total: {len(qa_list)}, Need browser retrieval: {len(needs)}")

    summary = asyncio.run(unlock_mod.run_batch(
        config, adapter, needs,
        batch_size=getattr(args, "batch_size", 5),
        headless=getattr(args, "headless", False),
        screenshots_on_failure=not getattr(args, "no_screenshots", False),
    ))

    if emit_json:
        print(json.dumps(summary))
    else:
        print(f"\n  Done! Success: {summary['success']}, Failed: {summary['failed']}")

    return 0 if summary.get("ok") else 1


# ── auth ───────────────────────────────────────────────────────────────────

def _cmd_auth(args: argparse.Namespace, emit_json: bool) -> int:
    from . import auth as auth_mod
    from . import config as config_mod

    cfg = config_mod.load(args.config)
    cfg = auth_mod.resolve(cfg)
    result = auth_mod.doctor_auth(cfg)
    result["base_domain"] = cfg["base_url"]
    result["proxy"] = auth_mod.redact_proxy(cfg.get("proxy"))

    if emit_json:
        print(json.dumps(result))
    else:
        status = "OK" if result["ok"] else "FAIL"
        print(f"  Auth status : {status}")
        print(f"  Source      : {result['auth_source']}")
        print(f"  Cookies     : {result['cookie_count']}")
        print(f"  XSRF found  : {result['xsrf_found']}")
        if result["required_cookies_missing"]:
            print(f"  Missing     : {', '.join(result['required_cookies_missing'])}")

    return 0 if result["ok"] else 30


# ── doctor ─────────────────────────────────────────────────────────────────

def _cmd_doctor(args: argparse.Namespace, emit_json: bool) -> int:
    from . import auth as auth_mod
    from . import config as config_mod
    from . import state as state_mod

    checks = []
    all_ok = True

    def check(name: str, ok: bool, message: str = "") -> None:
        nonlocal all_ok
        checks.append({"name": name, "ok": ok, "message": message})
        if not ok:
            all_ok = False
        if not emit_json:
            icon = "OK" if ok else "FAIL"
            msg = f" — {message}" if message else ""
            print(f"  [{icon}] {name}{msg}")

    # 1. config file
    config_file = getattr(args, "config", "config.json")
    check("config_exists", os.path.exists(config_file), "" if os.path.exists(config_file) else f"{config_file} not found")

    cfg = None
    if os.path.exists(config_file):
        try:
            cfg = config_mod.load(config_file)
            check("config_valid", True)
            check("base_url_set", "example.com" not in cfg["base_url"], cfg["base_url"])
            check("target_uid_set", bool(cfg["target_uid"]))
        except Exception as exc:
            check("config_valid", False, str(exc))

    # 2. auth
    if cfg:
        try:
            cfg = auth_mod.resolve(cfg)
            auth_result = auth_mod.doctor_auth(cfg)
            check("browser_auth", cfg.get("_auth_source", "").startswith("browser"),
                  cfg.get("_auth_source", "unknown"))
            check("required_cookies", not auth_result["required_cookies_missing"],
                  ", ".join(auth_result["required_cookies_missing"]) if auth_result["required_cookies_missing"] else "")
        except Exception as exc:
            check("auth_resolve", False, str(exc))

    # 3. playwright
    try:
        import playwright  # noqa: F401
        check("playwright_installed", True)
    except ImportError:
        check("playwright_installed", False, "run: py -m playwright install chromium")

    # 4. output dirs writable
    if cfg:
        for label, path in [("output_dir_writable", cfg["save_dir"]), ("qa_dir_writable", cfg["qa_save_dir"])]:
            try:
                os.makedirs(path, exist_ok=True)
                test = os.path.join(path, ".write_test")
                open(test, "w").close()
                os.remove(test)
                check(label, True)
            except Exception as exc:
                check(label, False, str(exc))

    # 5. state files readable
    if cfg:
        for label, path in [
            ("article_state_readable", os.path.join(cfg["save_dir"], "_state.json")),
            ("qa_state_readable", os.path.join(cfg["qa_save_dir"], "_state.json")),
        ]:
            if os.path.exists(path):
                try:
                    state_mod.load(path)
                    check(label, True)
                except Exception as exc:
                    check(label, False, str(exc))

    result = {"ok": all_ok, "checks": checks}
    if emit_json:
        print(json.dumps(result))
    else:
        print(f"\n  Overall: {'OK' if all_ok else 'FAIL'}")

    return 0 if all_ok else 1


# ── state ──────────────────────────────────────────────────────────────────

def _cmd_state(args: argparse.Namespace, emit_json: bool) -> int:
    from . import config as config_mod
    from . import state as state_mod

    cfg = config_mod.load(args.config)
    action = args.action or "inspect"

    if action == "inspect" and emit_json:
        result = {}
        for label, path in [
            ("articles", os.path.join(cfg["save_dir"], "_state.json")),
            ("qa", os.path.join(cfg["qa_save_dir"], "_state.json")),
        ]:
            if os.path.exists(path):
                s = state_mod.load(path)
                result[label] = {
                    "count": len(s.get("articles", {})) if label == "articles" else len(s.get("qa", {})),
                    "last_run": s.get("last_successful_run_at"),
                }
            else:
                result[label] = {"count": None, "last_run": None}
        print(json.dumps({"ok": True, "articles": result.get("articles"), "qa": result.get("qa")}))
        return 0

    for label, path in [
        ("articles", os.path.join(cfg["save_dir"], "_state.json")),
        ("qa", os.path.join(cfg["qa_save_dir"], "_state.json")),
    ]:
        if action == "inspect":
            if os.path.exists(path):
                s = state_mod.load(path)
                print(f"  {label}: {len(s.get('articles', {}))} articles, "
                      f"{len(s.get('qa', {}))} Q&A — last run: {s.get('last_successful_run_at', 'never')}")
            else:
                print(f"  {label}: no state file at {path}")

        elif action == "reset":
            if os.path.exists(path):
                os.remove(path)
                if not emit_json:
                    print(f"  Deleted: {path}")
            else:
                if not emit_json:
                    print(f"  Not found: {path}")

    return 0


# ── shared helpers ─────────────────────────────────────────────────────────

def _print_banner(config: Dict[str, Any]) -> None:
    from .auth import redact_proxy
    print("=" * 60)
    print("  PaywallFetcher")
    print("=" * 60)
    print(f"  Target   : {config.get('target_uid', 'unknown')}")
    print(f"  Base URL : {config.get('base_url', 'unknown')}")
    print(f"  Auth     : {config.get('_auth_source', 'unknown')}")
    print(f"  Proxy    : {redact_proxy(config.get('proxy'))}")
    print("=" * 60)


def _verify_login(session: Any, config: Dict[str, Any], adapter: Any) -> None:
    import requests
    print("\n[Verifying login...]")
    try:
        url = adapter.build_profile_url(config)
        r = session.get(url, timeout=config.get("request_timeout", 20))
        if r.status_code == 200:
            user = r.json().get("data", {}).get("user", {})
            print(f"  OK — target: {user.get('screen_name', 'unknown')}")
        else:
            from .errors import AuthError
            raise AuthError(f"Login verification failed: HTTP {r.status_code}. Session may have expired.")
    except requests.RequestException as exc:
        from .errors import NetworkError
        raise NetworkError(f"Login verification request failed: {exc}") from exc


def _save_article_index(refs: List[Any], save_dir: str) -> None:
    path = os.path.join(save_dir, "_article_list.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump([r.__dict__ for r in refs], f, ensure_ascii=False, indent=2)


def _save_qa_index(refs: List[Any], save_dir: str) -> None:
    path = os.path.join(save_dir, "_qa_list.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump([r.__dict__ for r in refs], f, ensure_ascii=False, indent=2)


def _print_summary(summary: Dict[str, Any]) -> None:
    print(f"\n{'='*60}")
    print("  Done!")
    print(f"{'='*60}")
    print(f"  Success : {summary.get('success', 0)}")
    print(f"  Failed  : {summary.get('failed', 0)}")
    print(f"  Skipped : {summary.get('skipped', 0)}")
    print(f"  Output  : {summary.get('saved_to', '')}")
    print(f"{'='*60}")
