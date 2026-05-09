"""Shared pytest fixtures live here."""

import os

import pytest


@pytest.fixture
def real_api_key():
    """Fixture that provides GEMINI_API_KEY from environment.

    Skips the test if the key is not available.
    """
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        pytest.skip("GEMINI_API_KEY not set")
    return key
