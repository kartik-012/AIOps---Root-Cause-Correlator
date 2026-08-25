"""WebSocket endpoint for live incident streaming."""

import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# In-memory connection manager (will be enhanced later)
active_connections: list[WebSocket] = []


@router.websocket("/ws/incidents")
async def incident_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time incident updates."""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Keep connection alive, wait for messages from client
            data = await websocket.receive_text()
            # Echo back for now (will be replaced with real event pushing)
            await websocket.send_text(json.dumps({"type": "ack", "data": data}))
    except WebSocketDisconnect:
        active_connections.remove(websocket)


async def broadcast_event(event: dict):
    """Broadcast an event to all connected WebSocket clients."""
    message = json.dumps(event)
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_text(message)
        except Exception:
            disconnected.append(connection)
    for conn in disconnected:
        active_connections.remove(conn)
