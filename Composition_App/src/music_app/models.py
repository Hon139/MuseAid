"""Data models for notes, rests, and sequences."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path


# Chromatic scale note names in order (sharps only, no flats)
CHROMATIC_NOTES = [
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"
]

# Frequencies for octaves 4 and 5 (A4 = 440 Hz standard tuning)
NOTE_FREQUENCIES: dict[str, float] = {
    "C4": 261.63, "C#4": 277.18, "D4": 293.66, "D#4": 311.13,
    "E4": 329.63, "F4": 349.23, "F#4": 369.99, "G4": 392.00,
    "G#4": 415.30, "A4": 440.00, "A#4": 466.16, "B4": 493.88,
    "C5": 523.25, "C#5": 554.37, "D5": 587.33, "D#5": 622.25,
    "E5": 659.25, "F5": 698.46, "F#5": 739.99, "G5": 783.99,
    "G#5": 830.61, "A5": 880.00, "A#5": 932.33, "B5": 987.77,
}

# Ordered list of all supported pitches for indexing
PITCH_ORDER = [
    "C4", "C#4", "D4", "D#4", "E4", "F4", "F#4", "G4", "G#4", "A4", "A#4", "B4",
    "C5", "C#5", "D5", "D#5", "E5", "F5", "F#5", "G5", "G#5", "A5", "A#5", "B5",
]

# Key signatures: number of sharps (positive) or flats (negative)
# Maps key name to (num_accidentals, is_sharps)
KEY_SIGNATURES: dict[str, tuple[int, bool]] = {
    "C": (0, True),   "Am": (0, True),
    "G": (1, True),   "Em": (1, True),
    "D": (2, True),   "Bm": (2, True),
    "A": (3, True),   "F#m": (3, True),
    "E": (4, True),   "C#m": (4, True),
    "B": (5, True),   "G#m": (5, True),
    "F#": (6, True),  "D#m": (6, True),
    "F": (1, False),  "Dm": (1, False),
    "Bb": (2, False), "Gm": (2, False),
    "Eb": (3, False), "Cm": (3, False),
    "Ab": (4, False), "Fm": (4, False),
    "Db": (5, False), "Bbm": (5, False),
    "Gb": (6, False), "Ebm": (6, False),
}

# Order of sharps and flats on the treble clef staff
# Staff positions for key signature sharps (F#, C#, G#, D#, A#, E#)
SHARP_POSITIONS = [4, 1, 5, 2, -1, 3, 0]  # F5, C5, G5, D5, A4, E5, B4
# Staff positions for key signature flats (Bb, Eb, Ab, Db, Gb, Cb)
FLAT_POSITIONS = [0, 3, -1, 2, -2, 1, -3]  # B4, E5, A4, D5, G4, C5, F4


class NoteType(str, Enum):
    """Duration types for notes and rests."""
    WHOLE = "whole"          # 4 beats
    HALF = "half"            # 2 beats
    QUARTER = "quarter"      # 1 beat
    EIGHTH = "eighth"        # 0.5 beats
    SIXTEENTH = "sixteenth"  # 0.25 beats

    @property
    def beats(self) -> float:
        """Return the duration in beats."""
        return {
            NoteType.WHOLE: 4.0,
            NoteType.HALF: 2.0,
            NoteType.QUARTER: 1.0,
            NoteType.EIGHTH: 0.5,
            NoteType.SIXTEENTH: 0.25,
        }[self]


def pitch_to_folder_name(pitch: str) -> str:
    """Convert a pitch like 'C#4' to a folder name like 'instrument_c_sharp'."""
    note_name = pitch[:-1]  # strip octave number
    folder_name = note_name.lower().replace("#", "_sharp")
    return f"instrument_{folder_name}"


def pitch_to_filename(pitch: str) -> str:
    """Convert a pitch like 'C#4' to a filename like 'c_sharp4'."""
    return pitch.lower().replace("#", "_sharp")


@dataclass
class Note:
    """A single musical note or rest in a sequence.

    Attributes:
        pitch: Note name with octave (e.g. 'C4'), or 'REST' for a rest.
        duration: Duration in beats. 1.0 = quarter note.
        beat: Position in the sequence in beats, starting from 0.0.
        note_type: Visual type (whole, half, quarter, eighth).
        instrument: Instrument identifier (0 = instrument 1, 1 = instrument 2).
    """

    pitch: str
    duration: float = 1.0
    beat: float = 0.0
    note_type: str = "quarter"
    instrument: int = 0

    @property
    def is_rest(self) -> bool:
        """Return True if this is a rest."""
        return self.pitch == "REST"

    def pitch_index(self) -> int:
        """Return the index of this note's pitch in PITCH_ORDER."""
        if self.is_rest:
            return -1
        return PITCH_ORDER.index(self.pitch)

    def get_note_type(self) -> NoteType:
        """Return the NoteType enum value."""
        return NoteType(self.note_type)


@dataclass
class Sequence:
    """An ordered collection of notes with a tempo, time signature, and key.

    Attributes:
        name: Display name for the sequence.
        bpm: Tempo in beats per minute.
        time_sig_num: Time signature numerator (beats per measure).
        time_sig_den: Time signature denominator (beat unit).
        key: Key signature name (e.g. 'C', 'G', 'F', 'Am').
        notes: List of Note objects, ordered by beat position.
    """

    name: str = "Untitled"
    bpm: int = 120
    time_sig_num: int = 4
    time_sig_den: int = 4
    key: str = "C"
    notes: list[Note] = field(default_factory=list)

    @property
    def beats_per_measure(self) -> int:
        """Number of beats in one measure."""
        return self.time_sig_num

    @property
    def key_info(self) -> tuple[int, bool]:
        """Return (num_accidentals, is_sharps) for the key signature."""
        return KEY_SIGNATURES.get(self.key, (0, True))

    def total_beats(self) -> float:
        """Return the total length of the sequence in beats."""
        if not self.notes:
            return 0.0
        last = max(self.notes, key=lambda n: n.beat + n.duration)
        return last.beat + last.duration

    def to_json(self) -> str:
        """Serialize the sequence to a JSON string."""
        data = {
            "name": self.name,
            "bpm": self.bpm,
            "time_sig_num": self.time_sig_num,
            "time_sig_den": self.time_sig_den,
            "key": self.key,
            "notes": [asdict(n) for n in self.notes],
        }
        return json.dumps(data, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> Sequence:
        """Deserialize a sequence from a JSON string."""
        data = json.loads(json_str)
        notes = [Note(**n) for n in data["notes"]]
        return cls(
            name=data["name"],
            bpm=data["bpm"],
            time_sig_num=data.get("time_sig_num", 4),
            time_sig_den=data.get("time_sig_den", 4),
            key=data.get("key", "C"),
            notes=notes,
        )

    @classmethod
    def from_file(cls, path: Path) -> Sequence:
        """Load a sequence from a JSON file."""
        return cls.from_json(path.read_text(encoding="utf-8"))

    def save(self, path: Path) -> None:
        """Save the sequence to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
