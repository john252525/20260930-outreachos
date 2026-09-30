"""Fixtures for dev-console integration tests."""

import pytest

BASE_URL = "http://127.0.0.1:48110"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires a running dev stack")
