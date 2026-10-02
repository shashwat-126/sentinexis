"""
Minimal in-memory WebSocket broadcast manager.

Good enough for a single incident-service instance (this platform's
deployment target). If incident-service is ever scaled horizontally, this
would need to move to a shared pub/sub (Redis is already in the stack and
would be the natural choice) -- noted here rather than silently pretending
this scales.
"""
from __future__ import annotations

import json

from fastapi import WebSocket

from shared.logger import setup_logger

logger = setup_logger("incident-service.ws")


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WebSocket connected. Active connections: {len(self.active)}")

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        logger.info(f"WebSocket disconnected. Active connections: {len(self.active)}")

    async def broadcast(self, event_type: str, payload: dict):
        message = json.dumps({"type": event_type, "data": payload}, default=str)
        stale = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


manager = ConnectionManager()
