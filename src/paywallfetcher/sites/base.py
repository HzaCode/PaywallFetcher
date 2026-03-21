"""SiteAdapter protocol and shared data classes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol, runtime_checkable


@dataclass
class ArticleRef:
    article_id: str
    title: str
    author: str
    post_id: str
    created_at: str
    summary: str
    cover_pic: str
    page_url: str


@dataclass
class ArticleContent:
    title: str
    content_html: str
    content_text: str
    images: List[str] = field(default_factory=list)


@dataclass
class QARef:
    id: str
    question: str
    questioner: str
    price_info: str
    author: str
    date: str
    summary: str


@dataclass
class QAContent:
    question: str
    answer: str
    answer_html: Optional[str]
    answer_status: str  # "present" | "empty" | "blocked" | "unknown"
    extraction_source: str  # "requests" | "browser"


@dataclass
class UnlockSelectors:
    trigger: str
    question: List[str]
    answer: List[str]


@runtime_checkable
class SiteAdapter(Protocol):
    """Protocol every site adapter must satisfy."""

    key: str

    def validate_config(self, config: dict) -> None:
        """Raise ConfigError if the config is missing required site fields."""
        ...

    def build_profile_url(self, config: dict) -> str:
        """Return the URL for the target user's profile API."""
        ...

    def build_article_list_url(self, config: dict, page: int) -> str:
        """Return the URL for a page of the article list."""
        ...

    def parse_article_list(self, payload: dict, config: dict) -> List[ArticleRef]:
        """Parse the article list API response into a list of ArticleRef."""
        ...

    def build_article_url(self, config: dict, article_id: str) -> str:
        """Return the URL for a single article page."""
        ...

    def extract_article(self, html: str) -> ArticleContent:
        """Extract article content from the HTML of an article page."""
        ...

    def build_qa_list_url(self, config: dict, page: int) -> str:
        """Return the URL for a page of the Q&A list."""
        ...

    def parse_qa_list(self, payload: dict) -> List[QARef]:
        """Parse the Q&A list API response into a list of QARef."""
        ...

    def build_qa_url(self, config: dict, qa_id: str) -> str:
        """Return the URL for a single Q&A page."""
        ...

    def extract_qa(self, html: str) -> QAContent:
        """Extract Q&A content from the HTML of a Q&A page."""
        ...

    def unlock_selectors(self) -> UnlockSelectors:
        """Return CSS/node-type selectors used during browser-assisted retrieval."""
        ...
