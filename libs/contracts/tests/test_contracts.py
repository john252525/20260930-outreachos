"""Round-trip and validation tests for contracts."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from contracts.brief import Brief, BriefIdentity
from contracts.contact import Contact
from contracts.events import EVENT_PAYLOAD_MAP, parse_event
from contracts.icp import ICP, ScoringWeights, Segment


def test_brief_minimal_roundtrip() -> None:
    brief = Brief(
        tenant_id=uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        identity=BriefIdentity(project_name="Test", language="ru"),
    )
    restored = Brief.model_validate_json(brief.model_dump_json())
    assert restored.id == brief.id
    assert restored.schema_version == "1.0"
    assert restored.completeness_score == 0.0


def test_brief_rejects_naive_datetime() -> None:
    with pytest.raises(ValidationError):
        Brief(
            tenant_id=uuid4(),
            created_at=datetime(2026, 1, 1),  # naive
            updated_at=datetime.now(UTC),
            identity=BriefIdentity(project_name="X"),
        )


def test_contact_ignores_extra_fields() -> None:
    data = {
        "tenant_id": str(uuid4()),
        "fingerprint": "fp",
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
        "unknown_field": "ignored",
    }
    c = Contact.model_validate(data)
    assert not hasattr(c, "unknown_field")


def test_scoring_weights_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        ScoringWeights(
            industry_match=0.5,
            size_match=0.5,
            geo_match=0.5,
            pain_match=0.5,
            trigger_match=0.5,
            role_match=0.5,
        )


def test_icp_with_segment_roundtrip() -> None:
    icp = ICP(
        tenant_id=uuid4(),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        brief_id=uuid4(),
        segments=[Segment(id=uuid4(), name="S1")],
    )
    restored = ICP.model_validate_json(icp.model_dump_json())
    assert restored.segments[0].name == "S1"


def test_parse_event_tenant_created() -> None:
    tid = uuid4()
    envelope = parse_event(
        "tenant.created",
        {
            "event_type": "tenant.created",
            "tenant_id": str(tid),
            "occurred_at": datetime.now(UTC).isoformat(),
            "producer": "test/0.1.0",
            "payload": {"tenant": {"id": str(tid), "name": "Acme", "status": "active"}},
        },
    )
    assert envelope.event_type == "tenant.created"
    assert envelope.payload.tenant.name == "Acme"


def test_event_registry_covers_all_subjects() -> None:
    assert "tenant.created" in EVENT_PAYLOAD_MAP
    assert "llm.called" in EVENT_PAYLOAD_MAP
    assert len(EVENT_PAYLOAD_MAP) >= 20
