"""Common test fixtures for Irrigation Computer."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):  # noqa: PT004
    """Enable loading of custom integrations in all tests."""
    yield


@pytest.fixture
def disable_persistent_notification():
    """Avoid hitting persistent_notification.create during tests."""
    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        wraps=None,
    ) as p:
        yield p
