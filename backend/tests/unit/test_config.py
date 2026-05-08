"""Unit tests for AppConfig."""

import pytest
from pydantic import ValidationError

from tour_guide.config import AppConfig


class TestAppConfig:
    """Tests for AppConfig."""

    def test_loads_gemini_api_key_from_env(self, monkeypatch):
        """With GEMINI_API_KEY=test-key in env, AppConfig loads correctly."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        config = AppConfig()
        assert config.gemini_api_key == "test-key"

    def test_default_values(self, monkeypatch):
        """Default values are set correctly."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        config = AppConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.poi_cache_dir == "/tmp/tour_guide_cache"
        assert config.narration_cache_dir == "/tmp/tour_guide_narration_cache"
        assert config.log_level == "INFO"

    def test_missing_gemini_api_key_raises_validation_error(self, monkeypatch):
        """Missing GEMINI_API_KEY raises ValidationError."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(ValidationError):
            AppConfig()
