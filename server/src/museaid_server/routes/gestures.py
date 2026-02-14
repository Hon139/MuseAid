"""POST /gestures — receive gesture events from the hand-gesture-app."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from ..services.gesture_map import map_gesture
from ..state import app_state

logger = logging.getLogger("museaid.routes.gestures")

router = APIRouter()


class GestureEvent(BaseModel):
    """Payload sent by the hand-gesture-app."""

    gesture: str
    confidence: float = 0.0
    timestamp: float = 0.0


@router.post("/gestures")
async def receive_gesture(event: GestureEvent) -> dict:
    """Map a gesture to a SequenceEditor command and broadcast it.

    ``toggle_playback`` is a special command handled entirely by the
    Composition App (it is not a SequenceEditor command), so it is
    broadcast without modifying the server-side sequence.
    """
    command = map_gesture(event.gesture)
    if command is None:
        logger.warning("Unknown gesture: %s", event.gesture)
        return {"status": "ignored", "reason": f"unknown gesture: {event.gesture}"}

    if command == "toggle_playback":
        # Playback control is a UI-only action — just forward to clients.
        await app_state.broadcast({"type": "command", "command": "toggle_playback"})
        logger.info("Broadcast toggle_playback")
        return {"status": "ok", "command": "toggle_playback"}

    # Apply the command to the server-side sequence.
    known = app_state.editor.execute(command)
    if not known:
        return {"status": "ignored", "reason": f"unknown command: {command}"}

    # Broadcast both the command (so the Composition App can animate)
    # and the updated sequence (so it stays in sync).
    await app_state.broadcast({
        "type": "command",
        "command": command,
        "cursor": app_state.editor.cursor,
    })

    logger.info(
        "Gesture %s -> command %s (cursor=%d)",
        event.gesture, command, app_state.editor.cursor,
    )
    return {"status": "ok", "command": command, "cursor": app_state.editor.cursor}
