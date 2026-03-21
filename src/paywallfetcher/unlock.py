"""Browser-assisted Q&A retrieval (Playwright).

Uses the authorized browser session to retrieve content accessible to
the logged-in account. Only use for content the user is authorized to access.

Prefer native OpenClaw browser tooling when available; this module provides
the repeatable local automation path.
"""

from __future__ import annotations

import asyncio
import html
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .auth import build_playwright_cookies
from .sites.base import SiteAdapter, UnlockSelectors


def is_already_retrieved(qa_dir: str) -> bool:
    """Return True when the existing qa.txt has a non-empty answer."""
    txt = os.path.join(qa_dir, "qa.txt")
    if not os.path.exists(txt):
        return False
    try:
        content = Path(txt).read_text(encoding="utf-8")
    except OSError:
        return False
    parts = content.split("=" * 60)
    answer = parts[-1].strip() if len(parts) > 1 else ""
    return bool(answer) and answer != "(empty)"


async def process_one(
    context: Any,
    config: Dict[str, Any],
    adapter: SiteAdapter,
    qa_info: Dict[str, Any],
    qa_dir: str,
    screenshots_on_failure: bool = True,
) -> Tuple[bool, str]:
    """Retrieve a single Q&A via browser. Returns (success, answer_status)."""
    os.makedirs(qa_dir, exist_ok=True)
    selectors: UnlockSelectors = adapter.unlock_selectors()
    qa_id = qa_info.get("id", "")
    question = qa_info.get("question", "")

    page = await context.new_page()
    try:
        url = adapter.build_qa_url(config, qa_id)
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(3)

        btn = page.locator(selectors.trigger)
        if await btn.count() > 0:
            await btn.click()
            await asyncio.sleep(4)

        answer_text = await _extract_text(page, selectors.answer)
        question_text = await _extract_text(page, selectors.question) or question

        print(f"  [{qa_id}] answer: {len(answer_text)} chars")

        _write_txt(qa_dir, qa_info, question_text, answer_text)
        _write_html(qa_dir, qa_info, question_text, answer_text)

        return True, "present" if answer_text else "empty"

    except Exception as exc:
        print(f"  [{qa_id}] FAILED: {exc}")
        if screenshots_on_failure:
            try:
                await page.screenshot(path=os.path.join(qa_dir, "failure.png"))
            except Exception:
                pass
        return False, "failed"
    finally:
        await page.close()


async def run_batch(
    config: Dict[str, Any],
    adapter: SiteAdapter,
    needs: List[Tuple[Dict[str, Any], str]],
    batch_size: int = 5,
    headless: bool = False,
    screenshots_on_failure: bool = True,
) -> Dict[str, Any]:
    """Run browser-assisted retrieval in parallel batches.

    Returns a run summary dict.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: py -m playwright install chromium"
        ) from exc

    playwright_cookies = build_playwright_cookies(config)
    run_summary: Dict[str, Any] = {
        "ok": True,
        "total": len(needs),
        "success": 0,
        "failed": 0,
        "items": [],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        ctx_args: Dict[str, Any] = {}
        proxy = config.get("proxy")
        if proxy:
            ctx_args["proxy"] = {"server": proxy}

        context = await browser.new_context(**ctx_args)
        if playwright_cookies:
            await context.add_cookies(playwright_cookies)

        print(f"  Browser launched. Cookies injected: {len(playwright_cookies)}")

        total = len(needs)
        for batch_start in range(0, total, batch_size):
            batch = needs[batch_start : batch_start + batch_size]
            print(f"\n  --- Batch {batch_start // batch_size + 1} ({len(batch)} items) ---")

            tasks = [
                process_one(context, config, adapter, qa_info, qa_dir, screenshots_on_failure)
                for qa_info, qa_dir in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (qa_info, qa_dir), result in zip(batch, results):
                if isinstance(result, Exception):
                    run_summary["failed"] += 1
                    run_summary["items"].append(
                        {"id": qa_info.get("id"), "status": "error", "error": str(result)}
                    )
                else:
                    ok, status = result
                    if ok:
                        run_summary["success"] += 1
                    else:
                        run_summary["failed"] += 1
                    run_summary["items"].append({"id": qa_info.get("id"), "status": status})

            await asyncio.sleep(2)

        await browser.close()

    run_summary["ok"] = run_summary["failed"] == 0
    return run_summary


# ── helpers ────────────────────────────────────────────────────────────────


async def _extract_text(page: Any, selectors: List[str]) -> str:
    js = f"""
        () => {{
            const sels = {json.dumps(selectors)};
            for (const s of sels) {{
                const el = document.querySelector(s);
                if (el) {{
                    const t = el.innerText.trim();
                    if (t.length > 0) return t;
                }}
            }}
            return '';
        }}
    """
    return await page.evaluate(js)


def _write_txt(qa_dir: str, qa_info: Dict[str, Any], question: str, answer: str) -> None:
    with open(os.path.join(qa_dir, "qa.txt"), "w", encoding="utf-8") as f:
        f.write(f"Question: {question or qa_info.get('question', '')}\n")
        if qa_info.get("questioner"):
            f.write(f"Questioner: {qa_info['questioner']}\n")
        if qa_info.get("price_info"):
            f.write(f"Price: {qa_info['price_info']}\n")
        if qa_info.get("date"):
            f.write(f"Date: {qa_info['date']}\n")
        f.write("=" * 60 + "\n\n")
        f.write(answer or "(empty)")


def _write_html(qa_dir: str, qa_info: Dict[str, Any], question: str, answer: str) -> None:
    eq = html.escape(question or qa_info.get("question", ""))
    answer_html = "".join(
        f"<p>{html.escape(line)}</p>" for line in answer.splitlines()
    ) if answer else "<p>(empty)</p>"

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Q&amp;A: {eq[:100]}</title>
    <style>
        body {{ max-width: 800px; margin: 40px auto; padding: 0 20px;
               font-family: -apple-system, sans-serif; line-height: 1.8; color: #333; }}
        .question {{ background: #f7f7f7; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .question h2 {{ font-size: 18px; margin: 0 0 10px; }}
        .meta {{ color: #999; font-size: 13px; }}
        .answer {{ padding: 20px 0; }}
        .footer {{ margin-top: 30px; padding-top: 15px; border-top: 1px solid #eee;
                   color: #aaa; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="question">
        <h2>{eq}</h2>
        <div class="meta">
            {html.escape(qa_info.get('questioner', ''))}
            {' | ' + html.escape(qa_info.get('price_info', '')) if qa_info.get('price_info') else ''}
            {' | ' + html.escape(qa_info.get('date', '')) if qa_info.get('date') else ''}
        </div>
    </div>
    <div class="answer">
        {answer_html}
    </div>
    <div class="footer">
        <p>Downloaded: {html.escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</p>
    </div>
</body>
</html>"""
    with open(os.path.join(qa_dir, "qa.html"), "w", encoding="utf-8") as f:
        f.write(html_out)
