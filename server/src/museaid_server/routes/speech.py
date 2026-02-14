"""POST /speech — receive transcribed text and send it to Gemini."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from ..models import Sequence
from ..services.gemini import edit_sequence
from ..state import app_state

logger = logging.getLogger("museaid.routes.speech")

router = APIRouter()


class SpeechPayload(BaseModel):
    """Payload sent by the speech-to-text pipeline."""

    text: str


@router.post("/speech")
async def receive_speech(payload: SpeechPayload) -> dict:
    """Process a speech transcription through Gemini and broadcast the result.

    Flow:
        1. Take the current sequence JSON from server state.
        2. Send it + the user's instruction to Gemini.
        3. Parse Gemini's response as a new Sequence.
        4. Replace the server state and broadcast to all clients.
    """
    instruction = payload.text.strip()
    if not instruction:
        return {"status": "ignored", "reason": "empty instruction"}

    current_json = app_state.sequence.to_json()
    logger.info("Speech instruction: %r", instruction)

    try:
        updated_json = await edit_sequence(current_json, instruction)
        new_sequence = Sequence.from_json(updated_json)
    except Exception:
        logger.exception("Gemini / parsing failed for instruction: %r", instruction)
        return {"status": "error", "reason": "failed to process instruction"}

    app_state.replace_sequence(new_sequence)

    await app_state.broadcast({
        "type": "sequence_update",
        "sequence": app_state.sequence_dict(),
    })

    logger.info("Sequence updated via speech — %d notes", len(new_sequence.notes))
    return {
        "status": "ok",
        "note_count": len(new_sequence.notes),
    }
