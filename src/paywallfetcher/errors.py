"""Custom exception hierarchy for PaywallFetcher.

Exit code contract:
  0  — success
  10 — no new content (incremental mode)
  20 — configuration error
  30 — authentication error
  40 — network error
  50 — extraction error
  60 — state file error
"""


class PaywallFetcherError(Exception):
    """Base class for all PaywallFetcher errors."""

    exit_code: int = 1


class ConfigError(PaywallFetcherError):
    """Configuration validation failed."""

    exit_code = 20


class AuthError(PaywallFetcherError):
    """Authentication or cookie resolution failed."""

    exit_code = 30


class NetworkError(PaywallFetcherError):
    """HTTP request failed or returned unexpected status."""

    exit_code = 40


class ExtractionError(PaywallFetcherError):
    """Content extraction from HTML failed."""

    exit_code = 50


class StateError(PaywallFetcherError):
    """State file read or write failed."""

    exit_code = 60


class NoNewContentError(PaywallFetcherError):
    """No new content found during incremental polling."""

    exit_code = 10
