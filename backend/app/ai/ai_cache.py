"""
Lightweight in-memory TTL cache for Siraj AI context.

Only caches read-only, non-sensitive data (financial context snapshots).
Never caches: AI responses, tool results, write-operation outputs, PII.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Any

logger = logging.getLogger("siraj.ai.cache")


@dataclass
class CacheEntry:
    """A single cached value with expiration timestamp."""
    value: Any
    expires_at: float
    created_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class ContextCache:
    """
    In-memory TTL cache for build_context() results.
    
    Keyed by user_id string. Each entry expires after `ttl_seconds`.
    Thread-safe for async usage (single-threaded event loop).
    
    Usage:
        cache = ContextCache(ttl_seconds=300)
        
        # Try cache first
        cached = cache.get(user_id)
        if cached is not None:
            context_str = cached
        else:
            context_str = await build_context(user_id, db)
            cache.set(user_id, context_str)
    """

    def __init__(self, ttl_seconds: int = 300):
        self._store: dict[str, CacheEntry] = {}
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[str]:
        """
        Retrieve a cached context string by user_id.
        Returns None on miss or expiry.
        """
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            logger.debug("Cache MISS for key=%s", key)
            return None

        if entry.is_expired:
            # Clean up expired entry
            del self._store[key]
            self._misses += 1
            logger.debug("Cache EXPIRED for key=%s (age=%.1fs)", key, time.time() - entry.created_at)
            return None

        self._hits += 1
        age = time.time() - entry.created_at
        logger.info(
            "Cache HIT for key=%s (age=%.1fs, ttl=%ds)",
            key, age, self._ttl
        )
        return entry.value

    def set(self, key: str, value: str) -> None:
        """Store a context string with TTL expiration."""
        now = time.time()
        self._store[key] = CacheEntry(
            value=value,
            expires_at=now + self._ttl,
            created_at=now,
        )
        logger.debug("Cache SET for key=%s (ttl=%ds)", key, self._ttl)

    def invalidate(self, key: str) -> None:
        """Remove a specific key from cache (e.g., after a write operation)."""
        if key in self._store:
            del self._store[key]
            logger.debug("Cache INVALIDATED for key=%s", key)

    def clear(self) -> None:
        """Clear all cached entries."""
        count = len(self._store)
        self._store.clear()
        logger.info("Cache CLEARED (%d entries removed)", count)

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        now = time.time()
        expired_keys = [k for k, v in self._store.items() if now > v.expires_at]
        for key in expired_keys:
            del self._store[key]
        if expired_keys:
            logger.debug("Cache cleanup: removed %d expired entries", len(expired_keys))
        return len(expired_keys)

    @property
    def stats(self) -> dict:
        """Return cache statistics for logging/monitoring."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(hit_rate, 1),
            "active_entries": len(self._store),
            "ttl_seconds": self._ttl,
        }


# Module-level singleton instance
_context_cache: Optional[ContextCache] = None


def get_context_cache(ttl_seconds: int = 300) -> ContextCache:
    """Get or create the singleton ContextCache instance."""
    global _context_cache
    if _context_cache is None:
        _context_cache = ContextCache(ttl_seconds=ttl_seconds)
        logger.info("ContextCache initialized (ttl=%ds)", ttl_seconds)
    return _context_cache
