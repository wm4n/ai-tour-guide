"""Tests for NarrationCache — filesystem-based audio/transcript cache."""

import time

from tour_guide.cache.narration_cache import NarrationCache


class TestNarrationCache:
    """Tests for the NarrationCache implementation."""

    def test_put_then_get_returns_same_bytes(self, tmp_path):
        """put(key, audio_bytes, transcript) then get(key) returns (audio_bytes, transcript)."""
        cache = NarrationCache(tmp_path)
        audio_bytes = b"\x00\x01\x02\x03" * 25  # 100 bytes of fake audio
        transcript = "故宮博物院始建於1925年。"

        cache.put("test_key", audio_bytes, transcript)
        result = cache.get("test_key")

        assert result is not None
        returned_audio, returned_transcript = result
        assert returned_audio == audio_bytes
        assert returned_transcript == transcript

    def test_nonexistent_key_returns_none(self, tmp_path):
        """get('nonexistent') returns None when cache is empty."""
        cache = NarrationCache(tmp_path)

        result = cache.get("nonexistent")

        assert result is None

    def test_lru_eviction_at_limit(self, tmp_path):
        """When total size exceeds max_size_mb, oldest entries are evicted."""
        # Use a very small limit (0.0001 MB = ~102 bytes) to trigger eviction easily
        cache = NarrationCache(tmp_path, max_size_mb=0.0001)

        audio_bytes_1 = b"x" * 60  # 60 bytes audio
        audio_bytes_2 = b"y" * 60  # 60 bytes audio
        audio_bytes_3 = b"z" * 60  # 60 bytes audio

        cache.put("key1", audio_bytes_1, "transcript one")
        # Small delay to ensure distinct atime for LRU ordering
        time.sleep(0.05)
        cache.put("key2", audio_bytes_2, "transcript two")
        time.sleep(0.05)
        # Adding key3 should push total size over limit and evict key1
        cache.put("key3", audio_bytes_3, "transcript three")

        # key1 should have been evicted (oldest access time)
        assert cache.get("key1") is None

        # key3 should still be present
        result3 = cache.get("key3")
        assert result3 is not None
        assert result3[0] == audio_bytes_3

    def test_cache_creates_directory(self, tmp_path):
        """NarrationCache creates nested directories if they don't exist."""
        cache_dir = tmp_path / "nested" / "audio" / "cache"
        assert not cache_dir.exists()

        NarrationCache(cache_dir)

        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_special_characters_in_key(self, tmp_path):
        """Keys with special characters (|, :, /) are properly sanitized."""
        cache = NarrationCache(tmp_path)
        audio_bytes = b"\x00" * 100
        transcript = "test transcript"

        # The standard narration cache key format includes | and :
        key = "osm:node:123|history_uncle|zh-TW|medium"
        cache.put(key, audio_bytes, transcript)
        result = cache.get(key)

        assert result is not None
        assert result[0] == audio_bytes
        assert result[1] == transcript

    def test_overwrite_same_key(self, tmp_path):
        """Putting the same key twice overwrites the previous value."""
        cache = NarrationCache(tmp_path)

        cache.put("key", b"\x01" * 50, "first transcript")
        cache.put("key", b"\x02" * 50, "second transcript")

        result = cache.get("key")
        assert result is not None
        assert result[0] == b"\x02" * 50
        assert result[1] == "second transcript"

    def test_get_updates_access_time_for_lru(self, tmp_path):
        """Accessing a key via get() updates its atime so it won't be evicted first."""
        cache = NarrationCache(tmp_path, max_size_mb=0.0003)  # ~307 bytes

        audio_1 = b"a" * 80
        audio_2 = b"b" * 80
        audio_3 = b"c" * 80

        cache.put("key1", audio_1, "transcript 1")
        time.sleep(0.05)
        cache.put("key2", audio_2, "transcript 2")

        # Access key1 to make it more recent than key2
        time.sleep(0.05)
        cache.get("key1")

        # Adding key3 should evict key2 (now the oldest accessed)
        time.sleep(0.05)
        cache.put("key3", audio_3, "transcript 3")

        # key2 should be evicted, key1 should still be present
        assert cache.get("key2") is None
        assert cache.get("key1") is not None
        assert cache.get("key3") is not None
