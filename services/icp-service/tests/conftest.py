"""Fixtures for icp-service integration tests."""

import uuid

import pytest

BASE_URL = "http://127.0.0.1:48104"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires a running dev stack")


@pytest.fixture
def tenant_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def headers(tenant_id: str, tenant_service_url: str) -> dict[str, str]:
    return {"X-Tenant-ID": tenant_id, "Idempotency-Key": str(uuid.uuid4())}


@pytest.fixture
def tenant_service_url() -> str:
    return "http://127.0.0.1:48100"
