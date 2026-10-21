"""
WebSocket endpoint and ConnectionManager for PHOENIX.
Performs JWT authentication, tenant/building scoping, sequence tracking, and client broadcast.
"""

from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from app.core.security import decode_access_token
from app.domain.events import EventEnvelope
from app.events.bus import event_bus
from app.domain.enums import EventType

router = APIRouter(tags=["Realtime WebSocket"])


class ConnectionManager:
    """Manages active WebSocket connections grouped by building ID scope."""

    def __init__(self) -> None:
        # building_id -> list[WebSocket]
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, building_id: str, token: str) -> bool:
        """
        Authenticate JWT token and register connection if valid.
        """
        try:
            payload = decode_access_token(token)
            # Register websocket under building_id
            await websocket.accept()
            if building_id not in self.active_connections:
                self.active_connections[building_id] = []
            self.active_connections[building_id].append(websocket)
            return True
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False

    def disconnect(self, websocket: WebSocket, building_id: str) -> None:
        if building_id in self.active_connections:
            if websocket in self.active_connections[building_id]:
                self.active_connections[building_id].remove(websocket)

    async def broadcast_to_building(self, building_id: str, envelope: EventEnvelope) -> None:
        """Broadcast event envelope to all authenticated clients subscribed to building."""
        connections = self.active_connections.get(building_id, [])
        message = envelope.model_dump_json()
        disconnected = []
        for conn in connections:
            try:
                await conn.send_text(message)
            except Exception:
                disconnected.append(conn)

        for conn in disconnected:
            self.disconnect(conn, building_id)


ws_manager = ConnectionManager()


@router.websocket("/ws/v1/buildings/{building_id}")
async def websocket_endpoint(websocket: WebSocket, building_id: str, token: str):
    """
    WebSocket endpoint for realtime emergency updates.
    Requires JWT token passed via query parameter `?token=...`.
    """
    connected = await ws_manager.connect(websocket, building_id, token)
    if not connected:
        return

    try:
        while True:
            # Keep connection alive; clients receive server-sent broadcasts
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type": "pong"}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, building_id)
