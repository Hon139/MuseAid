"""WebSocket /ws — real-time event stream to the Composition App."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..state import app_state

logger = logging.getLogger("museaid.routes.ws")

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """Accept a WebSocket connection and keep it alive.

    On connect the server immediately sends the current sequence so the
    client can synchronize.  After that the client just listens for
    broadcasts (commands and sequence updates pushed by other routes).

    The client may also send messages; currently these are logged but
    not acted upon (reserved for future use).
    """
    await ws.accept()
    app_state.register(ws)

    # Send the current state as the first message so the client is in sync.
    try:
        await ws.send_text(json.dumps({
            "type": "sequence_update",
            "sequence": app_state.sequence_dict(),
        }))
    except Exception:
        app_state.unregister(ws)
        return

    try:
        while True:
            # Keep the connection alive by reading messages.
            data = await ws.receive_text()
            logger.debug("WS received from client: %s", data[:200])
    except WebSocketDisconnect:
        pass
    finally:
        app_state.unregister(ws)
