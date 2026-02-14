"""Data models for notes, rests, and sequences.

Copied from Composition_App/src/music_app/models.py so the server can
manipulate sequences independently without importing the Qt-dependent package.
Keep in sync with the Composition_App version when the schema changes.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path


# Chromatic scale note names in order (sharps only, no flats)
CHROMATIC_NOTES = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
]

# Ordered list of all supported pitches for indexing
PITCH_ORDER = [
    "C4", "C#4", "D4", "D#4", "E4", "F4", "F#4", "G4", "G#4", "A4", "A#4", "B4",
    "C5", "C#5", "D5", "D#5", "E5", "F5", "F#5", "G5", "G#5", "A5", "A#5", "B5",
]


class NoteType(str, Enum):
    """Duration types for notes and rests."""

    WHOLE = "whole"       # 4 beats
    HALF = "half"         # 2 beats
    QUARTER = "quarter"   # 1 beat
    EIGHTH = "eighth"     # 0.5 beats

    @property
    def beats(self) -> float:
        return {
            NoteType.WHOLE: 4.0,
            NoteType.HALF: 2.0,
            NoteType.QUARTER: 1.0,
            NoteType.EIGHTH: 0.5,
        }[self]


@dataclass
class Note:
    """A single musical note or rest in a sequence."""

    pitch: str
    duration: float = 1.0
    beat: float = 0.0
    note_type: str = "quarter"
    instrument: int = 0

    @property
    def is_rest(self) -> bool:
        return self.pitch == "REST"

    def pitch_index(self) -> int:
        if self.is_rest:
            return -1
        return PITCH_ORDER.index(self.pitch)


@dataclass
class Sequence:
    """An ordered collection of notes with a tempo, time signature, and key."""

    name: str = "Untitled"
    bpm: int = 120
    time_sig_num: int = 4
    time_sig_den: int = 4
    key: str = "C"
    notes: list[Note] = field(default_factory=list)

    def total_beats(self) -> float:
        if not self.notes:
            return 0.0
        last = max(self.notes, key=lambda n: n.beat + n.duration)
        return last.beat + last.duration

    def to_dict(self) -> dict:
        """Serialize the sequence to a plain dict (JSON-safe)."""
        return {
            "name": self.name,
            "bpm": self.bpm,
            "time_sig_num": self.time_sig_num,
            "time_sig_den": self.time_sig_den,
            "key": self.key,
            "notes": [asdict(n) for n in self.notes],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> Sequence:
        """Deserialize from a plain dict."""
        notes = [Note(**n) for n in data.get("notes", [])]
        return cls(
            name=data.get("name", "Untitled"),
            bpm=data.get("bpm", 120),
            time_sig_num=data.get("time_sig_num", 4),
            time_sig_den=data.get("time_sig_den", 4),
            key=data.get("key", "C"),
            notes=notes,
        )

    @classmethod
    def from_json(cls, json_str: str) -> Sequence:
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, path: Path) -> Sequence:
        return cls.from_json(path.read_text(encoding="utf-8"))
