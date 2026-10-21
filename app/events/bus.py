"""
In-Memory Domain Event Bus and WebSocket Broadcaster for PHOENIX.
Dispatches domain events asynchronously using sequence numbers and scoped envelopes.
Does NOT depend on database transactions for realtime event dispatch.
"""

import asyncio
from typing import Callable, Coroutine, Any, Optional
from app.domain.events import EventEnvelope, DomainEvent
from app.domain.enums import EventType


class EventBus:
    """In-memory publish-subscribe event bus for domain events."""

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[Callable[[EventEnvelope], Coroutine[Any, Any, None]]]] = {}
        self._sequence_counter: int = 0
        self._lock = asyncio.Lock()

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[EventEnvelope], Coroutine[Any, Any, None]],
    ) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def publish(self, event: DomainEvent, scope: dict[str, str]) -> EventEnvelope:
        """
        Package domain event into an auditable event envelope with an incrementing sequence number.
        """
        async with self._lock:
            self._sequence_counter += 1
            seq = self._sequence_counter

        envelope = EventEnvelope(
            sequence=seq,
            event_type=event.event_type,
            scope=scope,
            payload=event.payload,
        )

        handlers = self._subscribers.get(event.event_type, [])
        for handler in handlers:
            try:
                await handler(envelope)
            except Exception:
                # Event dispatch failures should not crash publisher
                pass

        return envelope


# Global singleton instance of EventBus
event_bus = EventBus()
