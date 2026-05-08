"""Tests for POI cache service."""

import time

from freezegun import freeze_time

from tour_guide.cache.poi_cache import POICache


class TestPOICache:
    """Test the POI cache implementation."""

    def test_cache_hit_put_then_get(self, tmp_path):
        """Cache hit: put(key, value) then get(key) returns same value."""
        cache = POICache(tmp_path)
        test_data = {"id": "poi:1", "name": "Museum", "lat": 25.0455, "lon": 121.5681}

        cache.put("museum:taipei", test_data)
        result = cache.get("museum:taipei")

        assert result == test_data

    def test_cache_miss_returns_none(self, tmp_path):
        """Cache miss: get('nonexistent-key') returns None."""
        cache = POICache(tmp_path)

        result = cache.get("nonexistent-key")

        assert result is None

    def test_ttl_expiry_after_30_days(self, tmp_path):
        """TTL expiry: After 31 days, get(key) returns None."""
        cache = POICache(tmp_path)
        test_data = {"id": "poi:1", "name": "Museum"}

        # Put data at current time
        cache.put("museum:taipei", test_data)

        # Verify it's there
        assert cache.get("museum:taipei") == test_data

        # Simulate 31 days later
        with freeze_time("2026-06-09"):  # 31 days after 2026-05-09
            result = cache.get("museum:taipei")
            assert result is None

    def test_lru_eviction_when_exceeds_max_size(self, tmp_path):
        """LRU eviction: When total size exceeds max_size_mb, oldest entries are removed."""
        # Use small max_size_mb (0.0003 MB = ~300 bytes) - enough for 1-2 entries
        cache = POICache(tmp_path, max_size_mb=0.0003)

        # Put first entry
        large_data_1 = {"data": "x" * 100}
        cache.put("key1", large_data_1)
        assert cache.get("key1") is not None

        # Put second entry
        large_data_2 = {"data": "y" * 100}
        cache.put("key2", large_data_2)
        assert cache.get("key2") is not None

        # Put third entry (should trigger eviction of key1)
        large_data_3 = {"data": "z" * 100}
        cache.put("key3", large_data_3)

        # Key1 should be evicted (oldest access time)
        result1 = cache.get("key1")
        assert result1 is None

        # Key3 should still be available
        result3 = cache.get("key3")
        assert result3 == large_data_3

    def test_lru_eviction_respects_access_time(self, tmp_path):
        """LRU respects access time: accessing a key updates its atime."""
        cache = POICache(tmp_path, max_size_mb=0.0004)  # ~400 bytes

        data_1 = {"data": "a" * 100}
        data_2 = {"data": "b" * 100}

        cache.put("key1", data_1)
        cache.put("key2", data_2)

        # Access key1 to update its atime (making it less old)
        time.sleep(0.05)  # Small delay to ensure timestamp difference
        cache.get("key1")

        # Put key3 - should evict key2 (which is older now)
        data_3 = {"data": "c" * 100}
        cache.put("key3", data_3)

        assert cache.get("key1") is not None  # Still accessible
        assert cache.get("key2") is None  # Evicted as it's oldest
        assert cache.get("key3") is not None

    def test_multiple_puts_overwrite(self, tmp_path):
        """Multiple puts to same key overwrite previous value."""
        cache = POICache(tmp_path)

        cache.put("key", {"value": 1})
        assert cache.get("key") == {"value": 1}

        cache.put("key", {"value": 2})
        assert cache.get("key") == {"value": 2}

    def test_cache_creates_directory(self, tmp_path):
        """Cache initialization creates the cache directory if it doesn't exist."""
        cache_dir = tmp_path / "nested" / "cache" / "dir"
        assert not cache_dir.exists()

        POICache(cache_dir)

        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_various_data_types(self, tmp_path):
        """Cache can store various data types (dict, list, str, int, etc.)."""
        cache = POICache(tmp_path)

        test_cases = [
            ("dict", {"a": 1, "b": 2}),
            ("list", [1, 2, 3, 4]),
            ("string", "hello world"),
            ("number", 42),
            ("float", 3.14),
            ("bool", True),
            ("null", None),
            ("nested", {"items": [1, 2, {"deep": "value"}]}),
        ]

        for key, value in test_cases:
            cache.put(key, value)
            assert cache.get(key) == value

    def test_special_characters_in_key(self, tmp_path):
        """Keys with special characters are properly encoded."""
        cache = POICache(tmp_path)
        test_data = {"id": "poi:1"}

        # Keys with special characters that need sanitization
        special_keys = [
            "key/with/slashes",
            "key:with:colons",
            "key|with|pipes",
            "key/with:multiple|special",
        ]

        for key in special_keys:
            cache.put(key, test_data)
            assert cache.get(key) == test_data
