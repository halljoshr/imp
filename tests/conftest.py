"""Shared test fixtures."""

import pytest
from pydantic_ai import models


@pytest.fixture(autouse=True)
def _prevent_real_api_calls() -> None:
    """Safety: block real API calls in all tests."""
    original = models.ALLOW_MODEL_REQUESTS
    models.ALLOW_MODEL_REQUESTS = False
    yield
    models.ALLOW_MODEL_REQUESTS = original
