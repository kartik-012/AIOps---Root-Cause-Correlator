"""WebSocket endpoint and async pub/sub event bus for live incident streaming."""

import asyncio
from contextlib import asynccontextmanager
import json
from typing import Any, AsyncIterator
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# Connected WebSocket clients
active_connections: list[WebSocket] = []

# In-process pub/sub subscriber queues (used by GraphQL Subscriptions & internal listeners)
_subscriber_queues: set[asyncio.Queue[dict[str, Any]]] = set()


@asynccontextmanager
async def subscribe_incident_events(maxsize: int = 100) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
    """Register an async queue to receive real-time incident events from broadcast_event()."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)
    _subscriber_queues.add(queue)
    try:
        yield queue
    finally:
        _subscriber_queues.discard(queue)


@router.websocket("/ws/incidents")
async def incident_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time incident updates."""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(json.dumps({"type": "ack", "data": data}))
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)


async def broadcast_event(event: dict[str, Any]) -> None:
    """Broadcast an event to all connected WebSocket clients and GraphQL Subscription queues."""
    message = json.dumps(event)
    disconnected: list[WebSocket] = []
    for connection in list(active_connections):
        try:
            await connection.send_text(message)
        except Exception:
            disconnected.append(connection)
    for conn in disconnected:
        if conn in active_connections:
            active_connections.remove(conn)

    # Fan out to any active GraphQL Subscription queues without blocking
    for q in list(_subscriber_queues):
        if q.full():
            try:
                q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass
