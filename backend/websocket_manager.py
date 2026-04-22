"""
Real-time WebSocket connection manager.
Maintains two pools: authenticated staff connections and public lobby connections.
"""
import json
from typing import Set
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._staff: Set[WebSocket] = set()
        self._lobby: Set[WebSocket] = set()

    async def connect_staff(self, ws: WebSocket):
        await ws.accept()
        self._staff.add(ws)

    async def connect_lobby(self, ws: WebSocket):
        await ws.accept()
        self._lobby.add(ws)

    def disconnect(self, ws: WebSocket):
        self._staff.discard(ws)
        self._lobby.discard(ws)

    async def broadcast_staff(self, event: str, data: dict):
        """Send to all authenticated staff clients."""
        await self._send_all(self._staff, event, data)

    async def broadcast_lobby(self, event: str, data: dict):
        """Send sanitized (no PHI) events to public lobby displays."""
        await self._send_all(self._lobby, event, data)

    async def broadcast_all(self, event: str, staff_data: dict, lobby_data: dict = None):
        """Send full data to staff, sanitized data to lobby."""
        await self._send_all(self._staff, event, staff_data)
        await self._send_all(self._lobby, event, lobby_data or _sanitize(staff_data))

    async def _send_all(self, pool: Set[WebSocket], event: str, data: dict):
        msg = json.dumps({"event": event, **data})
        dead = set()
        for ws in pool:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        pool -= dead


def _sanitize(data: dict) -> dict:
    """Strip PHI fields before sending to public lobby."""
    safe_keys = {
        "esi_level", "priority", "room_assignment", "routing_destination",
        "wait_time_estimate", "timestamp", "status",
    }
    return {k: v for k, v in data.items() if k in safe_keys}


manager = ConnectionManager()
