"""Change detection cache for tracking seen products."""

import contextlib
import hashlib
import logging
import time

from .models import ProductMatch

logger = logging.getLogger(__name__)


class MatchCache:
    """Cache for tracking seen product matches to avoid duplicate notifications.

    Supports both file-backed (via diskcache) and in-memory modes.
    """

    def __init__(
        self,
        cache_path: str | None = None,
        ttl_hours: int = 24,
    ):
        self.ttl_seconds = ttl_hours * 3600
        self._cache: dict[str, float] = {}
        self._disk_cache = None

        if cache_path:
            try:
                import diskcache  # type: ignore[import-untyped]

                self._disk_cache = diskcache.Cache(cache_path)
                logger.info(f"Using disk cache at {cache_path}")
            except Exception as e:
                logger.warning(f"Failed to initialize disk cache: {e}. Using memory.")

    def _make_key(self, match: ProductMatch) -> str:
        """Create a unique key for a product match."""
        # Key based on SKU + matching variant SKUs + in-stock status
        variant_info = sorted(
            f"{v.sku}:{v.in_stock}:{v.quantity or 0}" for v in match.matching_variants
        )
        content = f"{match.product.sku}|{'|'.join(variant_info)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def is_new(self, match: ProductMatch) -> bool:
        """Check if a match is new (not seen within TTL)."""
        key = self._make_key(match)
        now = time.time()

        # Check disk cache first
        if self._disk_cache is not None:
            try:
                timestamp = self._disk_cache.get(key)
                if timestamp is not None and now - timestamp < self.ttl_seconds:
                    return False
            except Exception as e:
                logger.warning(f"Disk cache read error: {e}")

        # Check memory cache
        timestamp = self._cache.get(key)
        return not (timestamp is not None and now - timestamp < self.ttl_seconds)

    def mark_seen(self, match: ProductMatch) -> None:
        """Mark a match as seen."""
        key = self._make_key(match)
        now = time.time()

        # Store in memory
        self._cache[key] = now

        # Store on disk if available
        if self._disk_cache is not None:
            try:
                self._disk_cache.set(key, now, expire=self.ttl_seconds)
            except Exception as e:
                logger.warning(f"Disk cache write error: {e}")

    def filter_new(self, matches: list[ProductMatch]) -> list[ProductMatch]:
        """Filter matches to only those that are new."""
        new_matches = []
        for match in matches:
            if self.is_new(match):
                new_matches.append(match)
                self.mark_seen(match)
        return new_matches

    def cleanup(self) -> None:
        """Remove expired entries from memory cache."""
        now = time.time()
        expired_keys = [
            k for k, v in self._cache.items() if now - v >= self.ttl_seconds
        ]
        for k in expired_keys:
            del self._cache[k]

    def close(self) -> None:
        """Close disk cache if open."""
        if self._disk_cache is not None:
            with contextlib.suppress(Exception):
                self._disk_cache.close()
