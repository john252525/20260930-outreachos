"""Fixtures for linkedin-sender tests."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires a running dev stack")
