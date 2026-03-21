"""Generic site adapter.

All site-specific selectors, API paths, and extraction logic live here.
The main pipeline in articles.py / qa.py knows nothing about site internals.
Configure api_paths in config.json to match the target site.
"""

from __future__ import annotations

import re
from typing import List

from bs4 import BeautifulSoup

from .base import (
    ArticleContent,
    ArticleRef,
    QAContent,
    QARef,
    UnlockSelectors,
)


class GenericAdapter:
    key = "generic"

    def validate_config(self, config: dict) -> None:
        from ..errors import ConfigError

        site = config.get("site", config)
        if not site.get("base_url") and not config.get("base_url"):
            raise ConfigError("site.base_url is required")
        if not site.get("target_uid") and not config.get("target_uid"):
            raise ConfigError("site.target_uid is required")

    def _base_url(self, config: dict) -> str:
        return (config.get("site") or config).get("base_url", config.get("base_url", "")).rstrip("/")

    def _uid(self, config: dict) -> str:
        return (config.get("site") or config).get("target_uid", config.get("target_uid", ""))

    def _api_paths(self, config: dict) -> dict:
        site = config.get("site") or {}
        return site.get("api_paths") or config.get("api_paths") or {}

    def build_profile_url(self, config: dict) -> str:
        tpl = self._api_paths(config).get("profile", "/ajax/profile/info?uid={uid}")
        return self._base_url(config) + tpl.format(uid=self._uid(config))

    def build_article_list_url(self, config: dict, page: int) -> str:
        tpl = self._api_paths(config).get(
            "articles",
            "/ajax/statuses/articles?uid={uid}&page={page}&feature=10",
        )
        return self._base_url(config) + tpl.format(uid=self._uid(config), page=page)

    def parse_article_list(self, payload: dict, config: dict) -> List[ArticleRef]:
        base_url = self._base_url(config)
        tpl = self._api_paths(config).get("article_page", "/article/p/show?id={article_id}")
        refs: List[ArticleRef] = []
        for item in payload.get("data", {}).get("list", []):
            pi = item.get("page_info", {})
            if pi.get("type") == "24" or pi.get("object_type") == "article":
                article_id = pi.get("page_id", "")
                if not article_id:
                    continue
                refs.append(
                    ArticleRef(
                        article_id=article_id,
                        title=pi.get("content1", "") or item.get("text_raw", "")[:50],
                        author=item.get("user", {}).get("screen_name", ""),
                        post_id=item.get("id", ""),
                        created_at=item.get("created_at", ""),
                        summary=item.get("text_raw", ""),
                        cover_pic=pi.get("page_pic", ""),
                        page_url=base_url + tpl.format(article_id=article_id),
                    )
                )
        return refs

    def build_article_url(self, config: dict, article_id: str) -> str:
        tpl = self._api_paths(config).get("article_page", "/article/p/show?id={article_id}")
        return self._base_url(config) + tpl.format(article_id=article_id)

    def extract_article(self, html: str) -> ArticleContent:
        soup = BeautifulSoup(html, "html.parser")
        title = ""
        title_el = soup.find("div", class_="title") or soup.find("h1")
        if title_el:
            title = title_el.get_text(strip=True)

        content_html = ""
        images: List[str] = []

        m = re.search(r'filterXSS\("(.*?)"\s*(?:,|\))', html, re.DOTALL)
        if m:
            raw = m.group(1)
            try:
                decoded = raw.encode("utf-8").decode("unicode_escape")
            except Exception:
                decoded = raw
            decoded = decoded.replace("\\/" , "/").replace('\\"', '"').replace("\\'", "'")
            content_html = decoded
            inner = BeautifulSoup(decoded, "html.parser")
            for img in inner.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                if src:
                    if src.startswith("//"):
                        src = "https:" + src
                    if not src.startswith("data:") and "emotion" not in src:
                        images.append(src)

        if not content_html:
            div = soup.find("div", id="article_content") or soup.find("div", class_="article_content")
            if div and div.get_text(strip=True):
                content_html = str(div)

        content_text = BeautifulSoup(content_html, "html.parser").get_text("\n", strip=True) if content_html else ""
        return ArticleContent(
            title=title,
            content_html=content_html,
            content_text=content_text,
            images=images,
        )

    def build_qa_list_url(self, config: dict, page: int) -> str:
        tpl = self._api_paths(config).get(
            "articles",
            "/ajax/statuses/articles?uid={uid}&page={page}&feature=10",
        )
        return self._base_url(config) + tpl.format(uid=self._uid(config), page=page)

    def parse_qa_list(self, payload: dict) -> List[QARef]:
        refs: List[QARef] = []
        seen: set = set()
        for item in payload.get("data", {}).get("list", []):
            pi = item.get("page_info", {})
            aid = pi.get("page_id", "")
            if (pi.get("object_type") == "wenda" or pi.get("source_type") == "wenda") and aid and aid not in seen:
                seen.add(aid)
                refs.append(
                    QARef(
                        id=aid,
                        question=pi.get("content1") or pi.get("page_desc") or "",
                        questioner=pi.get("content3", ""),
                        price_info=pi.get("content2", ""),
                        author=item.get("user", {}).get("screen_name", ""),
                        date=item.get("created_at", ""),
                        summary=item.get("text_raw", ""),
                    )
                )
        return refs

    def build_qa_url(self, config: dict, qa_id: str) -> str:
        tpl = self._api_paths(config).get("qa_page", "/p/{qa_id}")
        return self._base_url(config) + tpl.format(qa_id=qa_id)

    def extract_qa(self, html: str) -> QAContent:
        soup = BeautifulSoup(html, "html.parser")
        q_div = soup.find(class_="ask_con") or soup.find(attrs={"node-type": "askTitle"})
        question = q_div.get_text("\n", strip=True) if q_div else ""

        answer = ""
        a_div = soup.find(class_="main_answer") or soup.find(class_="WB_answer_wrap")
        if a_div:
            answer = a_div.get_text("\n", strip=True)

        status = "present" if answer else "empty"
        return QAContent(
            question=question,
            answer=answer,
            answer_html=str(a_div) if a_div else None,
            answer_status=status,
            extraction_source="requests",
        )

    def unlock_selectors(self) -> UnlockSelectors:
        return UnlockSelectors(
            trigger='[node-type="free_look_btn"]',
            question=[".ask_con", '[node-type="askTitle"]'],
            answer=[
                ".answer_con",
                ".answer_text",
                '[node-type="answer_content"]',
                '[node-type="answer_text"]',
                ".main_answer .WB_text",
                ".main_answer",
                ".WB_answer_wrap",
            ],
        )
