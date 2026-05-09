"""NarrationCache — filesystem-based cache for narration audio and transcripts with LRU eviction."""

import json
from pathlib import Path

_MAX_BYTES_DEFAULT = 500 * 1024 * 1024  # 500 MB


class NarrationCache:
    """Filesystem-based cache for narration audio blobs and transcripts.

    Features:
    - Persistent storage: audio as binary files, metadata as JSON
    - LRU eviction when max_size_mb is exceeded
    - Safe key handling with special character sanitization
    """

    def __init__(self, cache_dir: str | Path, max_size_mb: float = 500.0):
        """Initialize the NarrationCache.

        Args:
            cache_dir: Directory path for cache storage.
            max_size_mb: Maximum cache size in megabytes. Default 500 MB.
        """
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._max_bytes = int(max_size_mb * 1024 * 1024)

    def _safe_key(self, key: str) -> str:
        """Sanitize a cache key for use as a filesystem filename."""
        return key.replace("/", "_").replace(":", "_").replace("|", "_")

    def _audio_path(self, key: str) -> Path:
        return self._dir / f"{self._safe_key(key)}.audio"

    def _meta_path(self, key: str) -> Path:
        return self._dir / f"{self._safe_key(key)}.meta.json"

    def get(self, key: str) -> tuple[bytes, str] | None:
        """Retrieve cached audio bytes and transcript for the given key.

        Args:
            key: The cache key.

        Returns:
            Tuple of (audio_bytes, transcript), or None if not found.
        """
        audio_path = self._audio_path(key)
        meta_path = self._meta_path(key)
        if not audio_path.exists() or not meta_path.exists():
            return None
        audio_path.touch()  # Update LRU access time
        audio_bytes = audio_path.read_bytes()
        meta = json.loads(meta_path.read_text())
        return audio_bytes, meta["transcript"]

    def put(self, key: str, audio_bytes: bytes, transcript: str) -> None:
        """Store audio bytes and transcript under the given key.

        Args:
            key: The cache key.
            audio_bytes: Raw audio data to cache.
            transcript: Text transcript to cache alongside the audio.
        """
        self._audio_path(key).write_bytes(audio_bytes)
        self._meta_path(key).write_text(json.dumps({"transcript": transcript}))
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        """Evict oldest entries (by access time) if cache exceeds max_size_mb."""
        audio_files = sorted(
            self._dir.glob("*.audio"),
            key=lambda p: p.stat().st_atime,
        )
        total = sum(p.stat().st_size for p in audio_files)
        # Also count meta files
        total += sum(
            (self._dir / (p.stem + ".meta.json")).stat().st_size
            for p in audio_files
            if (self._dir / (p.stem + ".meta.json")).exists()
        )
        while total > self._max_bytes and audio_files:
            oldest = audio_files.pop(0)
            meta = self._dir / (oldest.stem + ".meta.json")
            total -= oldest.stat().st_size
            oldest.unlink(missing_ok=True)
            if meta.exists():
                total -= meta.stat().st_size
                meta.unlink()
