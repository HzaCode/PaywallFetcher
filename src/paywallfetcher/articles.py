"""Article fetch pipeline.

Uses a SiteAdapter for all site-specific logic.
The pipeline itself only knows about pagination, state, and output.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

from . import state as state_mod
from .errors import NetworkError
from .output import download_images, save_article
from .sites.base import ArticleRef, SiteAdapter


def fetch_list(
    session: requests.Session,
    config: Dict[str, Any],
    adapter: SiteAdapter,
    max_pages: int = 200,
    stop_at_known_ids: Optional[Set[str]] = None,
) -> Tuple[List[ArticleRef], bool]:
    """Fetch article list. Returns (refs, stopped_early)."""
    page_delay = config.get("delay_between_pages", 1)
    timeout = config.get("request_timeout", 20)
    refs: List[ArticleRef] = []
    stopped_early = False

    for page in range(1, max_pages + 1):
        url = adapter.build_article_list_url(config, page)
        print(f"  Fetching page {page}...", end=" ", flush=True)
        try:
            r = session.get(url, timeout=timeout)
        except requests.RequestException as exc:
            raise NetworkError(f"Failed to fetch article list page {page}: {exc}") from exc

        if r.status_code != 200:
            print(f"HTTP {r.status_code}")
            break

        payload = r.json()
        page_refs = adapter.parse_article_list(payload, config)
        total_items = len(payload.get("data", {}).get("list", []))

        count = 0
        hit_known = False
        for ref in page_refs:
            if stop_at_known_ids is not None and ref.article_id in stop_at_known_ids:
                hit_known = True
                break
            refs.append(ref)
            count += 1

        print(f"found {count} articles (of {total_items} posts)")

        if hit_known:
            print("  Reached previously downloaded content, stopping early.")
            stopped_early = True
            break

        if total_items < 20:
            print("  Reached last page.")
            break

        time.sleep(page_delay)

    return refs, stopped_early


def deduplicate(refs: List[ArticleRef]) -> List[ArticleRef]:
    seen: Set[str] = set()
    result = []
    for ref in refs:
        if ref.article_id not in seen:
            seen.add(ref.article_id)
            result.append(ref)
    return result


def download_all(
    session: requests.Session,
    config: Dict[str, Any],
    adapter: SiteAdapter,
    refs: List[ArticleRef],
    state: Dict[str, Any],
    state_path: str,
    save_dir: str,
    start: int = 1,
    no_images: bool = False,
    emit_json: bool = False,
) -> Dict[str, Any]:
    """Download articles and persist state after each success."""
    delay = config.get("delay_between_articles", 2)
    timeout = config.get("request_timeout", 20)
    done_ids = state_mod.downloaded_article_ids(state)
    total = len(refs)
    success = fail = skip = 0
    items_json = []

    for idx, ref in enumerate(refs, 1):
        if idx < start:
            skip += 1
            continue
        if ref.article_id in done_ids:
            skip += 1
            if not emit_json:
                print(f"  [{idx}/{total}] skipped (already downloaded): {ref.title[:40]}")
            continue

        if not emit_json:
            print(f"\n  [{idx}/{total}] {ref.title[:55]}")

        try:
            r = session.get(ref.page_url, timeout=timeout)
            if r.status_code != 200:
                if not emit_json:
                    print(f"    FAILED: HTTP {r.status_code}")
                fail += 1
                continue

            content = adapter.extract_article(r.text)
            if not emit_json:
                print(f"    content: {len(content.content_text)} chars, {len(content.images)} images")

            article_dir = save_article(ref.__dict__, content, save_dir)

            if not no_images and content.images:
                n = download_images(session, content.images, os.path.join(article_dir, "images"))
                if not emit_json:
                    print(f"    images: {n}/{len(content.images)}")

            if ref.cover_pic:
                try:
                    cr = session.get(ref.cover_pic, timeout=10, stream=True)
                    if cr.status_code == 200:
                        with open(os.path.join(article_dir, "cover.jpg"), "wb") as f:
                            for chunk in cr.iter_content(8192):
                                f.write(chunk)
                except Exception:
                    pass

            if not emit_json:
                print(f"    saved: {article_dir}")

            success += 1
            state_mod.record_article(state, ref.article_id, title=ref.title)
            state_mod.save(state_path, state)

            if emit_json:
                items_json.append({"id": ref.article_id, "title": ref.title, "saved_to": article_dir})

        except Exception as exc:
            if not emit_json:
                print(f"    FAILED: {exc}")
            fail += 1

        if idx < total:
            time.sleep(delay)

    state_mod.mark_run(state)
    state_mod.save(state_path, state)

    summary = {"ok": True, "success": success, "failed": fail, "skipped": skip, "saved_to": save_dir}
    if emit_json:
        summary["items"] = items_json
    return summary
