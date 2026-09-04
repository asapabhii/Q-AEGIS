"""Shared pytest fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    """Reset the cached settings around every test.

    ``get_settings`` is ``lru_cache``d, so a test that changes the environment
    would otherwise leak its configuration into unrelated tests through the
    cached instance, and the resulting failure would depend on test ordering.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A test client over a freshly constructed application instance."""
    with TestClient(create_app()) as test_client:
        yield test_client
