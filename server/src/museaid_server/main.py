"""MuseAid coordination server — FastAPI entry point.

Start with::

    cd server
    uv run uvicorn museaid_server.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import gestures, sequence, speech, ws

# ── Logging ──────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-24s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="MuseAid Server",
    description=(
        "Central coordination server for the MuseAid music composition "
        "copilot.  Connects the hand-gesture-app, speech-to-text / Gemini "
        "pipeline, and the Composition App."
    ),
    version="0.1.0",
)

# Allow all origins so the desktop apps and local scripts can reach us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────

app.include_router(gestures.router)
app.include_router(speech.router)
app.include_router(sequence.router)
app.include_router(ws.router)


@app.get("/health")
async def health() -> dict:
    """Simple health-check endpoint."""
    return {"status": "ok"}
