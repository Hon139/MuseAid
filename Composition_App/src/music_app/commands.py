"""SequenceEditor — command interface for editing sequences.

Designed so a future backend can send simple string commands
like 'move_left', 'move_right', 'pitch_up', 'pitch_down'
without needing knowledge of the internal model.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from .models import Note, Sequence, PITCH_ORDER


def _note_type_for_duration(duration: float) -> str | None:
    """Return a canonical note_type string for supported durations."""
    mapping = {
        4.0: "whole",
        2.0: "half",
        1.0: "quarter",
        0.5: "eighth",
        0.25: "sixteenth",
    }
    for beats, name in mapping.items():
        if abs(duration - beats) < 1e-6:
            return name
    return None


class SequenceEditor(QObject):
    """Wraps a Sequence and provides a cursor + command API.

    Signals:
        cursor_changed(int): Emitted when the cursor index changes.
        sequence_changed(): Emitted when notes are added, removed, or modified.
    """

    cursor_changed = pyqtSignal(int)
    sequence_changed = pyqtSignal()

    def __init__(self, sequence: Sequence, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.sequence = sequence
        self._cursor: int = 0

    # ── Properties ───────────────────────────────────────────────

    @property
    def cursor(self) -> int:
        """Index of the currently selected note."""
        return self._cursor

    @cursor.setter
    def cursor(self, value: int) -> None:
        if not self.sequence.notes:
            self._cursor = 0
        else:
            self._cursor = max(0, min(value, len(self.sequence.notes) - 1))
        self.cursor_changed.emit(self._cursor)

    @property
    def current_note(self) -> Note | None:
        """Return the note at the cursor, or None if sequence is empty."""
        if self.sequence.notes and 0 <= self._cursor < len(self.sequence.notes):
            return self.sequence.notes[self._cursor]
        return None

    # ── Command Dispatch ─────────────────────────────────────────

    def execute(self, command: str) -> None:
        """Dispatch a command string to the appropriate method.

        Supported commands:
            move_left, move_right, pitch_up, pitch_down,
            delete_note, add_note, toggle_instrument
        """
        actions: dict[str, Callable[[], None]] = {
            "move_left": self.move_left,
            "move_right": self.move_right,
            "pitch_up": self.pitch_up,
            "pitch_down": self.pitch_down,
            "delete_note": self.delete_note,
            "add_note": self.add_note,
            "toggle_instrument": self.toggle_instrument,
            "split_note": self.split_note,
            "merge_note": self.merge_note,
            "make_rest": self.make_rest,
        }
        action = actions.get(command)
        if action is not None:
            action()

    # ── Navigation ───────────────────────────────────────────────

    def move_left(self) -> None:
        """Move the cursor one note to the left."""
        self.cursor = self._cursor - 1

    def move_right(self) -> None:
        """Move the cursor one note to the right."""
        self.cursor = self._cursor + 1

    # ── Pitch Editing ────────────────────────────────────────────

    def pitch_up(self) -> None:
        """Shift the selected note up one semitone."""
        note = self.current_note
        if note is None:
            return

        if note.is_rest:
            seed_idx = self._rest_seed_pitch_index()
            note.pitch = PITCH_ORDER[min(len(PITCH_ORDER) - 1, seed_idx + 1)]
            self.sequence_changed.emit()
            return

        idx = note.pitch_index()
        if idx < len(PITCH_ORDER) - 1:
            note.pitch = PITCH_ORDER[idx + 1]
            self.sequence_changed.emit()

    def pitch_down(self) -> None:
        """Shift the selected note down one semitone."""
        note = self.current_note
        if note is None:
            return

        if note.is_rest:
            seed_idx = self._rest_seed_pitch_index()
            note.pitch = PITCH_ORDER[max(0, seed_idx - 1)]
            self.sequence_changed.emit()
            return

        idx = note.pitch_index()
        if idx > 0:
            note.pitch = PITCH_ORDER[idx - 1]
            self.sequence_changed.emit()

    def _rest_seed_pitch_index(self) -> int:
        """Find a nearby non-rest pitch index to seed rest->note conversion."""
        if not self.sequence.notes:
            return 0

        # Prefer previous melodic context.
        for i in range(self._cursor - 1, -1, -1):
            n = self.sequence.notes[i]
            if not n.is_rest and n.pitch in PITCH_ORDER:
                return PITCH_ORDER.index(n.pitch)

        # Then look ahead.
        for i in range(self._cursor + 1, len(self.sequence.notes)):
            n = self.sequence.notes[i]
            if not n.is_rest and n.pitch in PITCH_ORDER:
                return PITCH_ORDER.index(n.pitch)

        return 0

    # ── Add / Remove ─────────────────────────────────────────────

    def delete_note(self) -> None:
        """Delete the note at the cursor position."""
        if not self.sequence.notes:
            return
        self.sequence.notes.pop(self._cursor)
        # Adjust cursor if it now points beyond the list
        if self._cursor >= len(self.sequence.notes) and self.sequence.notes:
            self._cursor = len(self.sequence.notes) - 1
        self.sequence_changed.emit()
        self.cursor_changed.emit(self._cursor)

    def add_note(self) -> None:
        """Insert a new quarter note (C4) after the cursor position."""
        if self.sequence.notes:
            current = self.sequence.notes[self._cursor]
            new_beat = current.beat + current.duration
        else:
            new_beat = 0.0

        new_note = Note(pitch="C4", duration=1.0, beat=new_beat, note_type="quarter", instrument=0)
        insert_idx = self._cursor + 1 if self.sequence.notes else 0
        self.sequence.notes.insert(insert_idx, new_note)
        self._cursor = insert_idx
        self.sequence_changed.emit()
        self.cursor_changed.emit(self._cursor)

    def toggle_instrument(self) -> None:
        """Toggle the selected note between instrument 1 and 2.

        Bound to Tab in the UI as a temporary editing command.
        """
        note = self.current_note
        if note is None:
            return
        note.instrument = 1 if note.instrument == 0 else 0
        self.sequence_changed.emit()

    def split_note(self) -> None:
        """Split current note into two notes with half duration each."""
        note = self.current_note
        if note is None:
            return
        if note.duration <= 0.25:
            return

        half_duration = note.duration / 2.0
        note.duration = half_duration
        mapped_type = _note_type_for_duration(half_duration)
        if mapped_type is not None:
            note.note_type = mapped_type

        # Keep same type for now; renderer uses duration for timing while note_type
        # remains the visual hint currently edited manually.
        new_note = Note(
            pitch=note.pitch,
            duration=half_duration,
            beat=note.beat + half_duration,
            note_type=note.note_type,
            instrument=note.instrument,
        )
        self.sequence.notes.insert(self._cursor + 1, new_note)
        self.sequence_changed.emit()
        self.cursor_changed.emit(self._cursor)

    def merge_note(self) -> None:
        """Merge current note with the next note on same instrument if adjacent."""
        if not self.sequence.notes or self._cursor >= len(self.sequence.notes) - 1:
            return

        cur = self.sequence.notes[self._cursor]
        nxt = self.sequence.notes[self._cursor + 1]

        if cur.instrument != nxt.instrument:
            return

        cur_end = cur.beat + cur.duration
        if abs(cur_end - nxt.beat) > 1e-6:
            return

        cur.duration += nxt.duration
        mapped_type = _note_type_for_duration(cur.duration)
        if mapped_type is not None:
            cur.note_type = mapped_type
        self.sequence.notes.pop(self._cursor + 1)
        self.sequence_changed.emit()
        self.cursor_changed.emit(self._cursor)

    def make_rest(self) -> None:
        """Convert the selected note into a rest (preserve duration/beat/instrument)."""
        note = self.current_note
        if note is None:
            return
        note.pitch = "REST"
        self.sequence_changed.emit()
