"""POST /speech — receive transcribed text and send it to Gemini."""

from __future__ import annotations

import logging
from dataclasses import asdict

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
    selection_start_index: int | None = None
    selection_end_index: int | None = None


def _validate_selection_range(length: int, start: int, end: int) -> tuple[bool, str | None]:
    if start < 0 or end < 0:
        return False, "selection indices must be non-negative"
    if start > end:
        return False, "selection_start_index must be <= selection_end_index"
    if length == 0:
        return False, "cannot apply selection-scoped edit to empty sequence"
    if end >= length:
        return False, f"selection_end_index {end} out of bounds for {length} notes"
    return True, None


def _strict_out_of_range_unchanged(
    before: Sequence,
    after: Sequence,
    selection_start: int,
    selection_end: int,
) -> tuple[bool, str | None]:
    if len(before.notes) != len(after.notes):
        return False, "strict selection mode requires unchanged total note count"

    for i, (old_note, new_note) in enumerate(zip(before.notes, after.notes, strict=False)):
        if selection_start <= i <= selection_end:
            continue
        if asdict(old_note) != asdict(new_note):
            return False, f"out-of-range mutation detected at note index {i}"

    return True, None


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

    selection_start = payload.selection_start_index
    selection_end = payload.selection_end_index
    scoped = selection_start is not None or selection_end is not None

    if scoped:
        if selection_start is None or selection_end is None:
            return {
                "status": "error",
                "reason": "selection_start_index and selection_end_index must both be provided",
            }

        ok, reason = _validate_selection_range(
            len(app_state.sequence.notes), selection_start, selection_end
        )
        if not ok:
            return {"status": "error", "reason": reason}

    current_sequence = app_state.sequence
    current_json = current_sequence.to_json()
    logger.info("Speech instruction: %r", instruction)

    try:
        updated_json = await edit_sequence(
            current_json,
            instruction,
            selection_start_index=selection_start,
            selection_end_index=selection_end,
        )
        new_sequence = Sequence.from_json(updated_json)
    except Exception:
        logger.exception("Gemini / parsing failed for instruction: %r", instruction)
        return {"status": "error", "reason": "failed to process instruction"}

    if selection_start is not None and selection_end is not None:
        ok, reason = _strict_out_of_range_unchanged(
            current_sequence,
            new_sequence,
            selection_start,
            selection_end,
        )
        if not ok:
            logger.warning(
                "Strict range check rejected speech update for selection [%d..%d]: %s",
                selection_start,
                selection_end,
                reason,
            )
            return {
                "status": "error",
                "reason": reason,
                "selection_start_index": selection_start,
                "selection_end_index": selection_end,
            }

    app_state.replace_sequence(new_sequence)

    await app_state.broadcast({
        "type": "sequence_update",
        "sequence": app_state.sequence_dict(),
    })

    logger.info("Sequence updated via speech — %d notes", len(new_sequence.notes))
    response = {
        "status": "ok",
        "note_count": len(new_sequence.notes),
    }
    if selection_start is not None and selection_end is not None:
        response["selection_start_index"] = selection_start
        response["selection_end_index"] = selection_end
    return response
