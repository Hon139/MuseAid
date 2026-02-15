"""Map hand-gesture-app gesture names to command strings.

Supports both:
- legacy gesture labels (e.g. ``PITCH_UP``)
- direct command-style labels (e.g. ``split_note`` or ``SPLIT_NOTE``)
"""

from __future__ import annotations

# Gesture name (from hand-gesture-app) -> command string
GESTURE_TO_COMMAND: dict[str, str] = {
    "PITCH_UP": "pitch_up",
    "PITCH_DOWN": "pitch_down",
    "TOGGLE_PLAYBACK": "toggle_playback",
    "SCROLL_FORWARD": "move_right",
    "SCROLL_BACKWARD": "move_left",
    "SWITCH_STAFF": "switch_edit_staff",
    "ADD_NOTE": "add_note",
    "DELETE_NOTE": "delete_note",
    # Keep gesture behavior aligned with keyboard Tab: cursor/lane switch only.
    "TOGGLE_INSTRUMENT": "switch_edit_staff",
    "SPLIT_NOTE": "split_note",
    "MERGE_NOTE": "merge_note",
    "MAKE_REST": "make_rest",
}

KNOWN_COMMANDS: set[str] = {
    "move_left",
    "move_right",
    "pitch_up",
    "pitch_down",
    "delete_note",
    "add_note",
    "toggle_instrument",
    "split_note",
    "merge_note",
    "make_rest",
    "toggle_playback",
    "switch_edit_staff",
}


def map_gesture(gesture: str) -> str | None:
    """Return command for *gesture*, or ``None`` if unknown."""
    if not gesture:
        return None

    # Legacy explicit map first.
    mapped = GESTURE_TO_COMMAND.get(gesture)
    if mapped is not None:
        return mapped

    # Allow direct command passthrough (already snake_case).
    if gesture in KNOWN_COMMANDS:
        return gesture

    # Allow SCREAMING_SNAKE gesture labels that match command names.
    candidate = gesture.lower()
    if candidate in KNOWN_COMMANDS:
        return candidate

    return None
