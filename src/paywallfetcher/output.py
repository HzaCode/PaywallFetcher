"""Output utilities: directory naming, HTML/TXT writing, image download."""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests

from .sites.base import ArticleContent, QAContent


def sanitize_filename(name: str, max_len: int = 80) -> str:
    name = re.sub(r'[\\/*?:"<>|\n\r\t]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:max_len]


def article_dir_name(article_id: str) -> str:
    return f"article_{article_id}"


def qa_dir_name(qa_id: str) -> str:
    return f"qa_{qa_id}"


def save_article(
    article_info: Dict[str, Any],
    content: ArticleContent,
    save_dir: str,
) -> str:
    title = content.title or article_info.get("title", f"article_{article_info.get('article_id', 'unknown')}")
    author = article_info.get("author", "")
    created_at = article_info.get("created_at", "")
    article_id = article_info.get("article_id", "")

    article_dir = os.path.join(save_dir, article_dir_name(article_id) if article_id else sanitize_filename(title))
    os.makedirs(article_dir, exist_ok=True)

    escaped_title = html.escape(title)
    escaped_author = html.escape(author)
    escaped_date = html.escape(created_at)

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>{escaped_title}</title>
    <style>
        body {{
            max-width: 800px; margin: 40px auto; padding: 0 20px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                         "Helvetica Neue", Arial, sans-serif;
            line-height: 1.8; color: #333; background: #fff;
        }}
        h1 {{ font-size: 24px; margin-bottom: 10px; }}
        .meta {{ color: #999; font-size: 13px; margin-bottom: 30px;
                 padding-bottom: 15px; border-bottom: 1px solid #eee; }}
        .article-body img {{ max-width: 100%; height: auto; margin: 10px 0; border-radius: 4px; }}
        .article-body p {{ margin: 12px 0; }}
        .footer {{ margin-top: 40px; padding-top: 15px; border-top: 1px solid #eee;
                   color: #aaa; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>{escaped_title}</h1>
    <div class="meta">
        {f'<span>Author: {escaped_author}</span>' if author else ''}
        {f' | <span>Date: {escaped_date}</span>' if created_at else ''}
    </div>
    <div class="article-body">
        {content.content_html or '<p>(empty)</p>'}
    </div>
    <div class="footer">
        <p>Downloaded: {html.escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</p>
    </div>
</body>
</html>"""

    with open(os.path.join(article_dir, "article.html"), "w", encoding="utf-8") as f:
        f.write(html_out)

    with open(os.path.join(article_dir, "article.txt"), "w", encoding="utf-8") as f:
        f.write(f"Title: {title}\n")
        if author:
            f.write(f"Author: {author}\n")
        if created_at:
            f.write(f"Date: {created_at}\n")
        f.write("=" * 60 + "\n\n")
        f.write(content.content_text or "(empty)")

    with open(os.path.join(article_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "title": title,
                "author": author,
                "created_at": created_at,
                "article_id": article_id,
                "content_length": len(content.content_text or ""),
                "image_count": len(content.images),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    return article_dir


def save_qa(
    qa_info: Dict[str, Any],
    content: QAContent,
    save_dir: str,
) -> str:
    qa_id = qa_info.get("id", "")
    question = content.question or qa_info.get("question", "")
    answer = content.answer or ""

    qa_dir = os.path.join(save_dir, qa_dir_name(qa_id) if qa_id else sanitize_filename(question[:60]))
    os.makedirs(qa_dir, exist_ok=True)

    escaped_q = html.escape(question)
    escaped_questioner = html.escape(qa_info.get("questioner", ""))
    escaped_price = html.escape(qa_info.get("price_info", ""))
    escaped_date = html.escape(qa_info.get("date", ""))

    answer_html_parts = "".join(
        f"<p>{html.escape(line)}</p>" for line in answer.splitlines()
    ) if answer else "<p>(empty)</p>"

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Q&amp;A: {escaped_q[:100]}</title>
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
        <h2>{escaped_q}</h2>
        <div class="meta">
            {f'Questioner: {escaped_questioner}' if escaped_questioner else ''}
            {f' | {escaped_price}' if escaped_price else ''}
            {f' | {escaped_date}' if escaped_date else ''}
        </div>
    </div>
    <div class="answer">
        {answer_html_parts}
    </div>
    <div class="footer">
        <p>Downloaded: {html.escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</p>
    </div>
</body>
</html>"""

    with open(os.path.join(qa_dir, "qa.html"), "w", encoding="utf-8") as f:
        f.write(html_out)

    with open(os.path.join(qa_dir, "qa.txt"), "w", encoding="utf-8") as f:
        f.write(f"Question: {question}\n")
        if qa_info.get("questioner"):
            f.write(f"Questioner: {qa_info['questioner']}\n")
        if qa_info.get("price_info"):
            f.write(f"Price: {qa_info['price_info']}\n")
        if qa_info.get("date"):
            f.write(f"Date: {qa_info['date']}\n")
        f.write("=" * 60 + "\n\n")
        f.write(answer or "(empty)")

    return qa_dir


def download_images(
    session: requests.Session,
    images: List[str],
    img_dir: str,
    timeout: int = 15,
) -> int:
    if not images:
        return 0
    os.makedirs(img_dir, exist_ok=True)
    count = 0
    for idx, url in enumerate(images):
        try:
            r = session.get(url, timeout=timeout, stream=True)
            if r.status_code != 200:
                continue
            ct = r.headers.get("content-type", "")
            if ct and not ct.startswith("image/"):
                continue
            ext = os.path.splitext(urlparse(url).path)[1]
            if not ext or len(ext) > 5:
                ext = ".jpg"
            with open(os.path.join(img_dir, f"img_{idx:03d}{ext}"), "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            count += 1
        except Exception as exc:
            print(f"    [image] failed #{idx}: {exc}")
    return count
