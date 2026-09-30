"""Custom SQLAlchemy types."""

from uuid import UUID

from sqlalchemy import TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Dialect
from uuid6 import uuid7


class UUID7(TypeDecorator[UUID]):
    """UUID stored as native PG UUID."""

    impl = PG_UUID(as_uuid=True)
    cache_ok = True

    def process_bind_param(self, value: UUID | None, dialect: Dialect) -> UUID | None:
        if value is None:
            return None
        if not isinstance(value, UUID):
            raise TypeError(f"Expected UUID, got {type(value)}")
        return value

    def process_result_value(self, value: UUID | None, dialect: Dialect) -> UUID | None:
        return value


def generate_uuid7() -> UUID:
    return uuid7()
