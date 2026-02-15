"""Gemini integration for AI-powered composition editing."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from google import genai

logger = logging.getLogger("museaid.gemini")

# Load workspace-level .env: `<repo>/.env`
load_dotenv(dotenv_path=Path(__file__).resolve().parents[4] / ".env")

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _load_extra_prompt() -> str:
    """Load optional workspace prompt appendix if present."""
    repo_root = Path(__file__).resolve().parents[4]
    candidates = [
        repo_root / "message (4).txt",
        repo_root / "message\\ (4).txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8").strip()
            except Exception:
                return ""
    return ""


_EXTRA_PROMPT = _load_extra_prompt()

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

if _EXTRA_PROMPT:
    SYSTEM_PROMPT = f"{SYSTEM_PROMPT}\n\n{_EXTRA_PROMPT}"


async def edit_sequence(
    current_sequence_json: str,
    instruction: str,
    selection_start_index: int | None = None,
    selection_end_index: int | None = None,
) -> str:
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
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY/GOOGLE_API_KEY in environment")

    range_rule = ""
    if selection_start_index is not None and selection_end_index is not None:
        range_rule = (
            "Selection constraints:\n"
            f"- Editable note indices are inclusive range [{selection_start_index}..{selection_end_index}].\n"
            "- You MUST NOT modify notes outside that range.\n"
            "- You MUST preserve note count and ordering outside that range exactly.\n"
            "- If instruction requests outside-range changes, ignore that part and still obey this constraint.\n\n"
        )

    prompt = (
        f"Current sequence JSON:\n{current_sequence_json}\n\n"
        f"User instruction:\n{instruction}\n\n"
        f"{range_rule}"
        "Return only the updated sequence JSON."
    )

    def _call_model() -> str:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                {"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{prompt}"}]},
            ],
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned empty response")
        return text

    raw_text = await asyncio.to_thread(_call_model)
    updated_json = _extract_json_object(raw_text)

    # Validate model output has expected schema before returning.
    parsed = json.loads(updated_json)
    required = {"name", "bpm", "time_sig_num", "time_sig_den", "key", "notes"}
    missing = required - set(parsed.keys())
    if missing:
        raise ValueError(f"Gemini output missing keys: {sorted(missing)}")

    return json.dumps(parsed)


def _extract_json_object(text: str) -> str:
    """Extract a JSON object from plain text or fenced markdown output."""
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text)
    if fenced:
        return fenced.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()

    raise ValueError("Could not parse JSON object from Gemini response")
