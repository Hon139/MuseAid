"""Map hand-gesture-app gesture names to SequenceEditor command strings.

The hand-gesture-app emits gestures like ``PITCH_UP``, ``SCROLL_FORWARD``,
etc.  This module translates them into the command strings accepted by
``SequenceEditor.execute()``, plus the special ``toggle_playback`` action
which the Composition App handles separately.
"""

from __future__ import annotations

# Gesture name (from hand-gesture-app) -> editor command string
GESTURE_TO_COMMAND: dict[str, str] = {
    "PITCH_UP": "pitch_up",
    "PITCH_DOWN": "pitch_down",
    "TOGGLE_PLAYBACK": "toggle_playback",
    "SCROLL_FORWARD": "move_right",
    "SCROLL_BACKWARD": "move_left",
    "SWITCH_STAFF": "switch_edit_staff",
}


def map_gesture(gesture: str) -> str | None:
    """Return the editor command for *gesture*, or ``None`` if unknown."""
    return GESTURE_TO_COMMAND.get(gesture)
