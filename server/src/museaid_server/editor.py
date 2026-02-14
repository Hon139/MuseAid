"""Server-side SequenceEditor — applies commands to a Sequence.

This is a simplified, non-Qt version of Composition_App's SequenceEditor.
It supports the same command strings so gesture-to-command mapping works
identically on the server.
"""

from __future__ import annotations

from typing import Callable

from .models import Note, Sequence, PITCH_ORDER


class SequenceEditor:
    """Wraps a Sequence and provides a cursor + command API.

    Unlike the Qt version this does not emit signals; instead the server
    reads the updated state after each command and broadcasts it.
    """

    def __init__(self, sequence: Sequence) -> None:
        self.sequence = sequence
        self._cursor: int = 0

    # ── Properties ───────────────────────────────────────────────

    @property
    def cursor(self) -> int:
        return self._cursor

    @cursor.setter
    def cursor(self, value: int) -> None:
        if not self.sequence.notes:
            self._cursor = 0
        else:
            self._cursor = max(0, min(value, len(self.sequence.notes) - 1))

    @property
    def current_note(self) -> Note | None:
        if self.sequence.notes and 0 <= self._cursor < len(self.sequence.notes):
            return self.sequence.notes[self._cursor]
        return None

    # ── Command Dispatch ─────────────────────────────────────────

    def execute(self, command: str) -> bool:
        """Dispatch a command string.  Returns True if the command was known."""
        actions: dict[str, Callable[[], None]] = {
            "move_left": self.move_left,
            "move_right": self.move_right,
            "pitch_up": self.pitch_up,
            "pitch_down": self.pitch_down,
            "delete_note": self.delete_note,
            "add_note": self.add_note,
            "toggle_instrument": self.toggle_instrument,
        }
        action = actions.get(command)
        if action is not None:
            action()
            return True
        return False

    # ── Navigation ───────────────────────────────────────────────

    def move_left(self) -> None:
        self.cursor = self._cursor - 1

    def move_right(self) -> None:
        self.cursor = self._cursor + 1

    # ── Pitch Editing ────────────────────────────────────────────

    def pitch_up(self) -> None:
        note = self.current_note
        if note is None or note.is_rest:
            return
        idx = note.pitch_index()
        if idx < len(PITCH_ORDER) - 1:
            note.pitch = PITCH_ORDER[idx + 1]

    def pitch_down(self) -> None:
        note = self.current_note
        if note is None or note.is_rest:
            return
        idx = note.pitch_index()
        if idx > 0:
            note.pitch = PITCH_ORDER[idx - 1]

    # ── Add / Remove ─────────────────────────────────────────────

    def delete_note(self) -> None:
        if not self.sequence.notes:
            return
        self.sequence.notes.pop(self._cursor)
        if self._cursor >= len(self.sequence.notes) and self.sequence.notes:
            self._cursor = len(self.sequence.notes) - 1

    def add_note(self) -> None:
        if self.sequence.notes:
            current = self.sequence.notes[self._cursor]
            new_beat = current.beat + current.duration
        else:
            new_beat = 0.0
        new_note = Note(pitch="C4", duration=1.0, beat=new_beat, note_type="quarter", instrument=0)
        insert_idx = self._cursor + 1 if self.sequence.notes else 0
        self.sequence.notes.insert(insert_idx, new_note)
        self._cursor = insert_idx

    def toggle_instrument(self) -> None:
        note = self.current_note
        if note is None:
            return
        note.instrument = 1 if note.instrument == 0 else 0
