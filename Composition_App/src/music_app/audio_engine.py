"""Audio engine — loads instrument samples and handles playback.

Uses pygame.mixer for WAV/MP3 playback and QTimer for beat-synchronised
sequential playback. Supports multiple instruments.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pygame
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .models import Note, Sequence


# One-folder-per-instrument layout (must match generate_samples.py)
# Example:
#   data/instrument_1/c4.wav
#   data/instrument_2/c4.wav
INSTRUMENT_DEFS = [
    {"name": "Sine (Instrument 1)", "folder": "instrument_1", "legacy_prefix": "instrument"},
    {"name": "Triangle (Instrument 2)", "folder": "instrument_2", "legacy_prefix": "instrument2"},
]
INSTRUMENT_NAMES = [d["name"] for d in INSTRUMENT_DEFS]
NOTE_BLEND_OVERLAP_RATIO = 0.30  # quarter @ 120 BPM => 500ms * 0.30 = 150ms
FLAT_TO_SHARP_EQUIV = {
    "CB": "B",
    "DB": "C#",
    "EB": "D#",
    "FB": "E",
    "GB": "F#",
    "AB": "G#",
    "BB": "A#",
    "E#": "F",
    "B#": "C",
}


class AudioEngine(QObject):
    """Loads instrument samples and plays sequences.

    Signals:
        note_playing(int): Emitted when a note starts playing (index in sequence).
        playback_finished(): Emitted when the full sequence has finished.
    """

    note_playing = pyqtSignal(int)
    playback_finished = pyqtSignal()

    def __init__(self, data_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data_dir = data_dir
        # samples[instrument_idx][pitch] = Sound
        self._samples: dict[int, dict[str, pygame.mixer.Sound]] = {}
        # samples_by_bank[folder_name][pitch] = Sound
        self._samples_by_bank: dict[str, dict[str, pygame.mixer.Sound]] = {}
        # default bank by instrument lane, configurable from UI
        self._default_sample_banks: dict[int, str | None] = {}
        self._auto_default_banks: dict[int, str | None] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._play_next)
        self._current_sequence: Sequence | None = None
        self._events: list[tuple[float, list[tuple[int, Note]]]] = []
        self._event_index: int = 0
        self._playing: bool = False
        self._channels: dict[int, any] = {}
        self._audio_available: bool = False

        # Try to initialize audio - gracefully handle failures
        try:
            # Only init the mixer subsystem — full pygame.init() conflicts with Qt on Windows
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=4096)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(32)
            self._channels[0] = pygame.mixer.Channel(0)
            self._channels[1] = pygame.mixer.Channel(1)
            self._audio_available = True
            print("Audio system initialized successfully")
        except pygame.error as e:
            print(f"Warning: Audio initialization failed: {e}")
            print("Running in silent mode - visual playback only")
            self._audio_available = False

        self._load_samples()

    def _load_samples(self) -> None:
        """Scan the data directory and load samples for all instruments."""
        if not self._audio_available:
            print("Audio not available - skipping sample loading")
            return
            
        if not self._data_dir.exists():
            print(f"Warning: Data directory {self._data_dir} does not exist.")
            return

        for inst_idx, inst in enumerate(INSTRUMENT_DEFS):
            self._samples[inst_idx] = {}
            folder = self._data_dir / inst["folder"]
            if folder.exists() and folder.is_dir():
                self._load_sample_files_from_folder(self._samples[inst_idx], folder)

            # Backward compatibility with legacy layout:
            # data/instrument_<note>/c4.wav, data/instrument2_<note>/c4.wav
            if not self._samples[inst_idx]:
                self._load_legacy_samples(inst_idx, inst["legacy_prefix"])

        # Load all one-folder-per-instrument banks for explicit JSON routing.
        # Any folder with a full note set can be targeted by note.sample_bank,
        # so folder names can be real instrument names (e.g. "piano", "violin").
        self._samples_by_bank = {}
        for folder in self._data_dir.iterdir():
            if not folder.is_dir():
                continue
            bank_samples: dict[str, pygame.mixer.Sound] = {}
            self._load_sample_files_from_folder(bank_samples, folder)
            # Ignore legacy per-note folders (usually 1-2 files each).
            if len(bank_samples) >= 8:
                self._samples_by_bank[folder.name] = bank_samples

        for idx, _ in enumerate(INSTRUMENT_DEFS):
            count = len(self._samples.get(idx, {}))
            print(f"Loaded {count} samples for {INSTRUMENT_NAMES[idx]}")

        if self._samples_by_bank:
            banks = ", ".join(sorted(self._samples_by_bank.keys()))
            print(f"Available sample banks: {banks}")

        # Initialize per-lane defaults. Prefer configured folders, otherwise
        # fall back to discovered banks by index so "Auto" always has a target.
        self._default_sample_banks = {}
        self._auto_default_banks = {}
        discovered_banks = sorted(self._samples_by_bank.keys())
        for inst_idx, inst in enumerate(INSTRUMENT_DEFS):
            folder = inst["folder"]
            auto_bank: str | None = None
            if folder in self._samples_by_bank:
                auto_bank = folder
            elif inst_idx < len(discovered_banks):
                auto_bank = discovered_banks[inst_idx]

            self._auto_default_banks[inst_idx] = auto_bank
            self._default_sample_banks[inst_idx] = auto_bank

    def available_sample_banks(self) -> list[str]:
        """Return discovered one-folder-per-instrument bank names."""
        return sorted(self._samples_by_bank.keys())

    def default_sample_bank(self, instrument: int) -> str | None:
        """Return current default bank for an instrument lane."""
        return self._default_sample_banks.get(instrument)

    def set_default_sample_bank(self, instrument: int, sample_bank: str | None) -> None:
        """Set lane default bank.

        - ``sample_bank`` set: use that explicit bank.
        - ``sample_bank`` is None: restore Auto bank for this lane.
        """
        if sample_bank and sample_bank in self._samples_by_bank:
            self._default_sample_banks[instrument] = sample_bank
        else:
            self._default_sample_banks[instrument] = None

    def _load_sample_files_from_folder(
        self,
        target: dict[str, pygame.mixer.Sound],
        folder: Path,
    ) -> None:
        """Load all supported audio files from a single instrument folder."""
        for sample_file in folder.iterdir():
            if not sample_file.is_file():
                continue
            ext = sample_file.suffix.lower()
            if ext not in (".wav", ".mp3", ".ogg"):
                continue
            pitch = self._filename_to_pitch(sample_file.stem)
            if not pitch:
                continue
            try:
                target[pitch] = pygame.mixer.Sound(str(sample_file))
            except pygame.error as e:
                print(f"Warning: Could not load {sample_file}: {e}")

    def _load_legacy_samples(self, inst_idx: int, prefix: str) -> None:
        """Load from legacy per-note folder structure."""
        for folder in self._data_dir.iterdir():
            if not folder.is_dir() or not folder.name.startswith(prefix + "_"):
                continue
            if prefix == "instrument" and folder.name.startswith("instrument2_"):
                continue
            self._load_sample_files_from_folder(self._samples[inst_idx], folder)

    @staticmethod
    def _filename_to_pitch(stem: str) -> str | None:
        """Convert a filename stem to a pitch string."""
        s = stem.replace("_sharp", "#")
        if len(s) < 2:
            return None
        if not s[-1].isdigit():
            return None
        return s[:-1].upper() + s[-1]

    def play_note(self, pitch: str, instrument: int = 0, sample_bank: str | None = None) -> None:
        """Play a single note sample on the selected instrument channel."""
        if pitch == "REST" or not self._audio_available:
            return

        # First priority: explicit per-note bank from JSON.
        # Second priority: per-lane default bank from UI.
        requested_bank = sample_bank or self._default_sample_banks.get(instrument)
        if requested_bank:
            bank_samples = self._samples_by_bank.get(requested_bank, {})
            sample_pitch = self._resolve_sample_pitch(pitch, bank_samples)
            sound = bank_samples.get(sample_pitch) if sample_pitch else None
            if sound is not None:
                sound.play()
                return

        # Use selected instrument bank, then fallback to instrument 1 bank.
        inst_samples = self._samples.get(instrument, {})
        sample_pitch = self._resolve_sample_pitch(pitch, inst_samples)
        sound = inst_samples.get(sample_pitch) if sample_pitch else None

        if sound is None and instrument != 0:
            fallback_samples = self._samples.get(0, {})
            sample_pitch = self._resolve_sample_pitch(pitch, fallback_samples)
            sound = fallback_samples.get(sample_pitch) if sample_pitch else None

        if sound is not None:
            # Use mixer-managed channel selection so previous notes can ring out
            # for their full sample duration without being cut off by the next note.
            sound.play()
        else:
            print(f"Warning: No sample for {pitch} (instrument {instrument})")

    @staticmethod
    def _resolve_sample_pitch(pitch: str, inst_samples: dict[str, any]) -> str | None:
        """Resolve requested pitch to an available sample key.

        Supports:
        - flats/enharmonic spellings -> sharps
        - octave lift/drop into available sample range
        """
        if pitch in inst_samples:
            return pitch
        if len(pitch) < 2 or not pitch[-1].isdigit():
            return None

        octave = int(pitch[-1])
        note_name = pitch[:-1].upper()
        note_name = FLAT_TO_SHARP_EQUIV.get(note_name, note_name)

        candidate = f"{note_name}{octave}"
        if candidate in inst_samples:
            return candidate

        # Prefer nearest in-range octave (sample set is typically C4..B5).
        if octave < 4:
            candidate = f"{note_name}4"
            if candidate in inst_samples:
                return candidate
        if octave > 5:
            candidate = f"{note_name}5"
            if candidate in inst_samples:
                return candidate

        # Final fallback: try both available octaves.
        for octv in (4, 5):
            candidate = f"{note_name}{octv}"
            if candidate in inst_samples:
                return candidate

        return None

    def play_sequence(self, sequence: Sequence, start_index: int = 0) -> None:
        """Start playing a sequence, optionally from a specific note index."""
        if self._playing:
            self.stop()
        self._current_sequence = sequence
        self._events = self._build_events(sequence)
        self._event_index = 0

        if self._events and sequence.notes:
            clamped_index = max(0, min(start_index, len(sequence.notes) - 1))
            start_beat = sequence.notes[clamped_index].beat
            for i, (beat, _) in enumerate(self._events):
                if beat >= start_beat:
                    self._event_index = i
                    break
            else:
                self._event_index = len(self._events) - 1

        if not self._events:
            self._playing = False
            self.playback_finished.emit()
            return

        self._playing = True
        self._play_current()

    def stop(self) -> None:
        """Stop any ongoing playback."""
        self._timer.stop()
        self._playing = False
        for channel in self._channels.values():
            channel.stop()

    @property
    def is_playing(self) -> bool:
        return self._playing

    def _play_current(self) -> None:
        """Play all notes in the current beat-group and schedule the next group."""
        seq = self._current_sequence
        if seq is None or self._event_index >= len(self._events):
            self._playing = False
            self.playback_finished.emit()
            return

        current_beat, grouped = self._events[self._event_index]

        if grouped:
            # Highlight first note from this beat group in the UI
            self.note_playing.emit(grouped[0][0])

        for _, note in grouped:
            self.play_note(note.pitch, note.instrument, note.sample_bank)

        # Schedule by distance to next beat group (enables simultaneous notes)
        if self._event_index + 1 < len(self._events):
            next_beat = self._events[self._event_index + 1][0]
            delta_beats = max(0.0, next_beat - current_beat)
            delta_ms = (60.0 / seq.bpm) * delta_beats * 1000
            overlap_ms = int(delta_ms * NOTE_BLEND_OVERLAP_RATIO)
            wait_ms = max(1, int(delta_ms) - overlap_ms)
            self._timer.start(wait_ms)
        else:
            # Last event: wait for longest note in group before finish
            longest = max((n.duration for _, n in grouped), default=0.0)
            wait_ms = max(1, int((60.0 / seq.bpm) * longest * 1000))
            self._timer.start(wait_ms)

    def _play_next(self) -> None:
        self._event_index += 1
        self._play_current()

    @staticmethod
    def _build_events(sequence: Sequence) -> list[tuple[float, list[tuple[int, Note]]]]:
        """Group notes by beat for simultaneous playback."""
        by_beat: dict[float, list[tuple[int, Note]]] = defaultdict(list)
        for i, note in enumerate(sequence.notes):
            by_beat[note.beat].append((i, note))
        return [(b, by_beat[b]) for b in sorted(by_beat.keys())]

    def cleanup(self) -> None:
        self._timer.stop()
        if self._audio_available:
            try:
                pygame.mixer.quit()
            except:
                pass  # Ignore cleanup errors
