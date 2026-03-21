"""Site adapter registry."""

from __future__ import annotations

from typing import Dict, Type

from .base import SiteAdapter
from .generic import GenericAdapter

_REGISTRY: Dict[str, Type[SiteAdapter]] = {
    "generic": GenericAdapter,
}


def get_adapter(site_kind: str) -> SiteAdapter:
    """Return a SiteAdapter instance for the given site_kind key."""
    cls = _REGISTRY.get(site_kind.lower())
    if cls is None:
        available = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown site_kind '{site_kind}'. Available adapters: {available}"
        )
    return cls()


__all__ = ["SiteAdapter", "get_adapter"]
