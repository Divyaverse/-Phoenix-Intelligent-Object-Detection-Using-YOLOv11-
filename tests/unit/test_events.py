"""
Unit tests for domain events and envelope structure.
"""

from app.domain.enums import EventType, RiskLevel
from app.domain.events import DomainEvent, EventScope, RiskUpdatedPayload


def test_domain_event_envelope_creation():
    """Verify DomainEvent envelope contains required sequence, scope, and payload fields."""
    scope = EventScope(organization_id="org_test", building_id="bld_test", floor_id="fl_01")
    payload = RiskUpdatedPayload(
        building_id="bld_test",
        floor_id="fl_01",
        global_risk_level=RiskLevel.HIGH,
        affected_nodes=["node_corridor_1"],
        active_hazards_count=1,
    )

    event = DomainEvent(
        event_type=EventType.RISK_UPDATED,
        sequence=1,
        scope=scope,
        payload=payload.model_dump(),
    )

    assert event.event_id.startswith("evt_")
    assert event.event_type == EventType.RISK_UPDATED
    assert event.sequence == 1
    assert event.scope.building_id == "bld_test"
    assert event.payload["global_risk_level"] == "HIGH"
