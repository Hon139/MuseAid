"""Generate placeholder WAV samples for each note and instrument.

Creates WAV files for two instruments:
  - Instrument 1 (sine wave): data/instrument_<note>/
  - Instrument 2 (triangle wave): data/instrument2_<note>/

Usage:
    uv run generate-samples
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import sawtooth

from .models import NOTE_FREQUENCIES, pitch_to_folder_name, pitch_to_filename

# Audio parameters
SAMPLE_RATE = 44100   # Hz
DURATION = 0.6        # seconds
AMPLITUDE = 0.4       # 0.0–1.0


def _make_envelope(n_samples: int, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Create a smooth ADSR-like envelope."""
    attack = int(0.02 * sample_rate)
    release = int(0.15 * sample_rate)
    env = np.ones(n_samples)
    if attack > 0:
        env[:attack] = np.linspace(0, 1, attack)
    if release > 0:
        env[-release:] = np.linspace(1, 0, release)
    return env


def _to_stereo_16bit(wave: np.ndarray) -> np.ndarray:
    """Convert a float mono waveform to stereo 16-bit integer."""
    mono = (wave * 32767).astype(np.int16)
    return np.column_stack((mono, mono))


def generate_sine(frequency: float) -> np.ndarray:
    """Generate a clean sine wave (instrument 1)."""
    n = int(SAMPLE_RATE * DURATION)
    t = np.linspace(0, DURATION, n, endpoint=False)
    wave = AMPLITUDE * np.sin(2 * np.pi * frequency * t) * _make_envelope(n)
    return _to_stereo_16bit(wave)


def generate_triangle(frequency: float) -> np.ndarray:
    """Generate a triangle wave (instrument 2) — warmer/softer tone."""
    n = int(SAMPLE_RATE * DURATION)
    t = np.linspace(0, DURATION, n, endpoint=False)
    wave = AMPLITUDE * sawtooth(2 * np.pi * frequency * t, width=0.5) * _make_envelope(n)
    return _to_stereo_16bit(wave)


INSTRUMENTS = {
    "instrument": generate_sine,       # Instrument 1 — sine
    "instrument2": generate_triangle,  # Instrument 2 — triangle
}


def _folder_for_instrument(instrument_prefix: str, pitch: str) -> str:
    """Build the folder name for a given instrument prefix and pitch."""
    note_name = pitch[:-1].lower().replace("#", "_sharp")
    return f"{instrument_prefix}_{note_name}"


def generate_all_samples(data_dir: Path) -> None:
    """Generate WAV samples for all notes across all instruments."""
    for prefix, gen_fn in INSTRUMENTS.items():
        for pitch, freq in NOTE_FREQUENCIES.items():
            folder_name = _folder_for_instrument(prefix, pitch)
            filename = pitch_to_filename(pitch) + ".wav"

            folder_path = data_dir / folder_name
            folder_path.mkdir(parents=True, exist_ok=True)

            file_path = folder_path / filename
            if file_path.exists():
                print(f"  Skipping {file_path} (already exists)")
                continue

            wave_data = gen_fn(freq)
            wavfile.write(str(file_path), SAMPLE_RATE, wave_data)
            print(f"  Created {file_path}")


def main() -> None:
    """Entry point for the generate-samples script."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            break
        current = current.parent
    else:
        print("Error: Could not find project root (pyproject.toml)", file=sys.stderr)
        sys.exit(1)

    data_dir = current / "data"
    print(f"Generating samples in {data_dir}...")
    generate_all_samples(data_dir)
    print("Done!")


if __name__ == "__main__":
    main()
