"""Shared application state for the MuseAid server.

Holds the canonical Sequence, the SequenceEditor, and a registry of
connected WebSocket clients so that any route can broadcast updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

from .editor import SequenceEditor
from .models import Sequence

logger = logging.getLogger("museaid.state")


class AppState:
    """Singleton-style application state shared across all routes."""

    def __init__(self) -> None:
        # Start with a minimal default sequence; the Composition App can
        # PUT its own on startup.
        self.sequence = Sequence(name="Untitled", bpm=120, notes=[])
        self.editor = SequenceEditor(self.sequence)
        self._clients: list[WebSocket] = []

    # ── WebSocket client management ──────────────────────────────

    def register(self, ws: WebSocket) -> None:
        self._clients.append(ws)
        logger.info("WebSocket client connected (%d total)", len(self._clients))

    def unregister(self, ws: WebSocket) -> None:
        if ws in self._clients:
            self._clients.remove(ws)
        logger.info("WebSocket client disconnected (%d total)", len(self._clients))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to every connected WebSocket client."""
        payload = json.dumps(message)
        stale: list[WebSocket] = []
        for ws in self._clients:
            try:
                await ws.send_text(payload)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self.unregister(ws)

    # ── Convenience helpers ──────────────────────────────────────

    def replace_sequence(self, new_seq: Sequence) -> None:
        """Replace the canonical sequence and reset the editor."""
        self.sequence = new_seq
        self.editor = SequenceEditor(self.sequence)

    def sequence_dict(self) -> dict:
        """Return the current sequence as a JSON-safe dict."""
        return self.sequence.to_dict()


# Module-level singleton used by all routes via dependency injection.
app_state = AppState()
