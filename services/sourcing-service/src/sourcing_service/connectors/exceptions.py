"""Connector error hierarchy."""


class ConnectorError(Exception):
    """Base connector error."""


class ConnectorUnavailableError(ConnectorError):
    """Connector unavailable (no keys, API down)."""


class ConnectorRateLimitError(ConnectorError):
    """Rate limit exhausted."""


class ConnectorAuthError(ConnectorError):
    """Authentication problem (bad key)."""
