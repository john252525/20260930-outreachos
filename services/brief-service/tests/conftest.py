"""Shared fixtures for brief-service tests."""

import os
import uuid

import pytest

BASE_URL = os.environ.get("BRIEF_BASE_URL", "http://127.0.0.1:48102")
TENANT_SERVICE_URL = os.environ.get("TENANT_BASE_URL", "http://127.0.0.1:48100")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires a running dev stack")


@pytest.fixture
def tenant_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def headers(tenant_id: str) -> dict[str, str]:
    return {"X-Tenant-ID": tenant_id, "Idempotency-Key": str(uuid.uuid4())}
