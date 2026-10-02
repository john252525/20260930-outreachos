"""Connector registry."""

from sourcing_service.connectors.base import Connector
from sourcing_service.connectors.exceptions import ConnectorUnavailableError


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, Connector] = {}

    def register(self, connector: Connector) -> None:
        if connector.name in self._connectors:
            raise ValueError(f"Connector already registered: {connector.name}")
        self._connectors[connector.name] = connector

    def get(self, name: str) -> Connector:
        if name not in self._connectors:
            raise ConnectorUnavailableError(f"Connector not registered: {name}")
        return self._connectors[name]

    def list_all(self) -> list[str]:
        return list(self._connectors.keys())

    def list_available(self) -> list[str]:
        return [name for name, c in self._connectors.items() if c.is_available]

    async def close_all(self) -> None:
        for c in self._connectors.values():
            await c.close()
