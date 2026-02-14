"""GET / PUT /sequence — read and update the canonical sequence state."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from ..models import Sequence
from ..state import app_state

logger = logging.getLogger("museaid.routes.sequence")

router = APIRouter()


@router.get("/sequence")
async def get_sequence() -> dict:
    """Return the current sequence as JSON.

    The Composition App calls this on startup to sync its local state.
    """
    return {
        "sequence": app_state.sequence_dict(),
        "cursor": app_state.editor.cursor,
    }


@router.put("/sequence")
async def put_sequence(body: dict) -> dict:
    """Replace the server-side sequence.

    Expected body::

        {
            "sequence": { "name": "...", "bpm": 120, ... , "notes": [...] }
        }

    The Composition App can call this to push its local state to the server
    (e.g. after loading a file or importing MIDI).
    """
    try:
        seq_data = body.get("sequence", body)
        new_seq = Sequence.from_dict(seq_data)
    except Exception:
        logger.exception("Invalid sequence payload")
        return {"status": "error", "reason": "invalid sequence data"}

    app_state.replace_sequence(new_seq)

    # Broadcast to other connected clients (if any).
    await app_state.broadcast({
        "type": "sequence_update",
        "sequence": app_state.sequence_dict(),
    })

    logger.info("Sequence replaced via PUT — %d notes", len(new_seq.notes))
    return {"status": "ok", "note_count": len(new_seq.notes)}
