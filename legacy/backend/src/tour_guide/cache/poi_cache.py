"""POI cache service with filesystem-based storage and LRU eviction."""

import json
import time
from pathlib import Path
from typing import Any

_TTL_SECONDS = 30 * 24 * 3600  # 30 days


class POICache:
    """Filesystem-based cache with TTL and LRU eviction policy.

    Features:
    - Persistent storage in JSON files
    - 30-day TTL for entries
    - LRU eviction when max_size_mb is exceeded
    - Safe key handling with special character sanitization
    """

    def __init__(self, cache_dir: str | Path, max_size_mb: float = 100.0):
        """Initialize the POI cache.

        Args:
            cache_dir: Directory path for cache storage.
            max_size_mb: Maximum cache size in megabytes. Default 100 MB.
        """
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_bytes = int(max_size_mb * 1024 * 1024)

    def _key_path(self, key: str) -> Path:
        """Convert a cache key to a safe filesystem path.

        Args:
            key: The cache key.

        Returns:
            Path object for the cache file.
        """
        # Sanitize key: replace special characters with underscores
        safe = key.replace("/", "_").replace(":", "_").replace("|", "_")
        return self._dir / f"{safe}.json"

    def get(self, key: str) -> Any | None:
        """Retrieve a value from the cache.

        Args:
            key: The cache key.

        Returns:
            The cached value, or None if not found or expired.
        """
        path = self._key_path(key)
        if not path.exists():
            return None

        # Load the cached data
        data = json.loads(path.read_text())

        # Check if TTL has expired
        if time.time() - data["written_at"] > _TTL_SECONDS:
            path.unlink(missing_ok=True)
            return None

        # Update access time for LRU tracking
        path.touch()
        return data["value"]

    def put(self, key: str, value: Any) -> None:
        """Store a value in the cache.

        Args:
            key: The cache key.
            value: The value to cache (must be JSON-serializable).
        """
        path = self._key_path(key)
        path.write_text(json.dumps({"written_at": time.time(), "value": value}))
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache exceeds max_size_mb."""
        files = sorted(self._dir.glob("*.json"), key=lambda p: p.stat().st_atime)
        total = sum(p.stat().st_size for p in files)

        # Keep evicting until cache size is within limits
        while total > self._max_bytes and files:
            oldest = files.pop(0)
            total -= oldest.stat().st_size
            oldest.unlink(missing_ok=True)
