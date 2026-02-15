"""WebSocket client that connects to the MuseAid server.

Runs in a background QThread so the Qt event loop is never blocked.
Emits Qt signals when commands or sequence updates arrive, which the
MainWindow connects to in order to update the editor and staff display.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger("museaid.client")

# Default server URL — override with MUSEAID_SERVER_WS env var.
_DEFAULT_WS_URL = "ws://localhost:8000/ws"


class ServerClient(QThread):
    """Background thread that maintains a WebSocket connection to the server.

    Signals
    -------
    command_received(str)
        Emitted when a ``{"type": "command", "command": "..."}`` message
        arrives.  The payload is the command string (e.g. ``"pitch_up"``).
    sequence_received(str)
        Emitted when a ``{"type": "sequence_update", "sequence": {...}}``
        message arrives.  The payload is the sequence dict serialized as
        a JSON string so it can cross the thread boundary safely.
    connected()
        Emitted when the WebSocket connection is established.
    disconnected()
        Emitted when the connection drops (will auto-reconnect).
    """

    command_received = pyqtSignal(str)
    sequence_received = pyqtSignal(str)
    connected = pyqtSignal()
    disconnected = pyqtSignal()

    def __init__(
        self,
        server_url: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._url = server_url or os.environ.get("MUSEAID_SERVER_WS", _DEFAULT_WS_URL)
        self._running = True
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws: Any | None = None

    # ── QThread entry point ──────────────────────────────────────

    def run(self) -> None:  # noqa: D401 — QThread override
        """Thread body — runs an asyncio event loop with reconnect logic."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._connect_loop())
        finally:
            self._loop = None
            loop.close()

    def stop(self) -> None:
        """Request a graceful shutdown of the background thread."""
        self._running = False

        # Proactively close the websocket from this thread so the async recv loop
        # wakes up immediately instead of waiting for network activity.
        loop = self._loop
        if loop and loop.is_running():
            def _request_ws_close() -> None:
                async def _close_ws() -> None:
                    if self._ws is not None:
                        try:
                            await self._ws.close()
                        except Exception:
                            pass

                asyncio.create_task(_close_ws())

            try:
                loop.call_soon_threadsafe(_request_ws_close)
            except RuntimeError:
                # Loop may already be shutting down.
                pass

        self.wait(3000)

    # ── Internals ────────────────────────────────────────────────

    async def _connect_loop(self) -> None:
        """Keep reconnecting until ``stop()`` is called."""
        import websockets

        while self._running:
            try:
                async with websockets.connect(self._url) as ws:
                    self._ws = ws
                    logger.info("Connected to server at %s", self._url)
                    self.connected.emit()
                    await self._listen(ws)
                    self._ws = None
            except Exception as exc:
                self._ws = None
                if not self._running:
                    return
                logger.warning("Connection lost (%s) — retrying in 2 s …", exc)
                self.disconnected.emit()
                # Wait before reconnecting, but check _running periodically.
                for _ in range(20):
                    if not self._running:
                        return
                    await asyncio.sleep(0.1)

    async def _listen(self, ws) -> None:
        """Read messages until the connection drops or we are stopped."""
        async for raw in ws:
            if not self._running:
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Non-JSON message from server: %s", raw[:200])
                continue

            msg_type = msg.get("type")

            if msg_type == "command":
                command = msg.get("command", "")
                if command:
                    self.command_received.emit(command)

            elif msg_type == "sequence_update":
                seq_data = msg.get("sequence")
                if seq_data is not None:
                    self.sequence_received.emit(json.dumps(seq_data))

            else:
                logger.debug("Unknown message type: %s", msg_type)
