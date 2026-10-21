"""
Unit tests for EventBus, EventEnvelope, sequence numbers, and WebSocket authorization.
"""

import pytest
import asyncio
from app.events.bus import EventBus
from app.domain.events import DomainEvent
from app.domain.enums import EventType
from app.core.security import create_access_token
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.mark.asyncio
async def test_event_bus_publishing_and_sequence():
    bus = EventBus()
    received_envelopes = []

    async def sample_handler(envelope):
        received_envelopes.append(envelope)

    bus.subscribe(EventType.RISK_UPDATED, sample_handler)

    event1 = DomainEvent(
        event_type=EventType.RISK_UPDATED,
        payload={"node_id": "node_n1", "risk": 0.85},
    )
    event2 = DomainEvent(
        event_type=EventType.RISK_UPDATED,
        payload={"node_id": "node_n2", "risk": 0.90},
    )

    scope = {"building_id": "bldg-hq-01"}
    env1 = await bus.publish(event1, scope)
    env2 = await bus.publish(event2, scope)

    assert env1.sequence == 1
    assert env2.sequence == 2
    assert len(received_envelopes) == 2
    assert received_envelopes[0].payload["risk"] == 0.85
    assert received_envelopes[1].payload["risk"] == 0.90


def test_websocket_connection_authorization():
    # Attempt connecting without token -> Rejected
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/v1/buildings/bldg-hq-01"):
            pass

    # Attempt connecting with valid JWT token -> Connected
    token = create_access_token("usr-test", "FIRST_RESPONDER", "org-test")
    with client.websocket_connect(f"/ws/v1/buildings/bldg-hq-01?token={token}") as websocket:
        websocket.send_text("ping")
        data = websocket.receive_text()
        assert data == '{"type": "pong"}'
