"""Placeholder Gemini integration for AI-powered composition editing.

This module defines the interface that a real Gemini integration would
implement.  For now it returns a stub response so the rest of the pipeline
can be tested end-to-end without an API key.

To plug in the real Google Generative AI SDK later:

    1. ``pip install google-generativeai``
    2. Set the ``GOOGLE_API_KEY`` environment variable.
    3. Replace the body of ``edit_sequence`` with a call to
       ``genai.GenerativeModel("gemini-pro").generate_content_async(prompt)``.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("museaid.gemini")

# ── System prompt sent to Gemini alongside the user instruction ──────

SYSTEM_PROMPT = """\
You are an expert music composition assistant.  You will receive a JSON
object describing a musical sequence (with fields: name, bpm,
time_sig_num, time_sig_den, key, notes) and a natural-language instruction
from the user.

Your job is to return **only** a valid JSON object with the same schema,
modified according to the instruction.  Do not include any explanation —
only the JSON.

Each note has: pitch (e.g. "C4", "REST"), duration (beats), beat
(start position), note_type ("whole"|"half"|"quarter"|"eighth"), and
instrument (0 or 1).
"""


async def edit_sequence(current_sequence_json: str, instruction: str) -> str:
    """Call Gemini to edit a sequence based on a natural-language instruction.

    Parameters
    ----------
    current_sequence_json:
        The current sequence serialized as a JSON string.
    instruction:
        The user's natural-language editing instruction (from speech-to-text).

    Returns
    -------
    str
        An updated sequence as a JSON string.  When the real model is
        connected this will be the model's output; for now it echoes the
        input unchanged with a log message.
    """
    logger.info(
        "Gemini placeholder called — instruction: %r (sequence unchanged)",
        instruction,
    )

    # ── Placeholder: echo input unchanged ────────────────────────
    # Replace this block with a real Gemini API call:
    #
    #   import google.generativeai as genai
    #   genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    #   model = genai.GenerativeModel("gemini-pro",
    #       system_instruction=SYSTEM_PROMPT)
    #   response = await model.generate_content_async(
    #       f"Current sequence:\n{current_sequence_json}\n\n"
    #       f"Instruction: {instruction}"
    #   )
    #   return response.text

    return current_sequence_json
