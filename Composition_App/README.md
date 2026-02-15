# Music App

A music production app with treble clef staff notation display, built with PyQt6.

## Features

- **Treble clef staff** — Renders notes on a standard 5-line musical staff with a treble clef
- **Multiple note/rest durations** — whole, half, quarter, eighth, and sixteenth note rendering
- **Playback cursor** — Vertical playback line with play/pause from cursor
- **JSON workflow** — Load/save compositions from the `examples/` directory
- **Dual edit cursors** — Toggle editing focus between two cursors plus playback cursor focus
- **Example files** — Includes `c_major_scale.json` and `megalovania_inspired.json`
- **Backend-ready** — `SequenceEditor` command interface for future external control (move_left, move_right, pitch_up, pitch_down, etc.)

## Quick Start

```bash
# Install dependencies
cd music-app
uv sync

# Generate placeholder sine-wave samples (only needed once)
uv run generate-samples

# Launch the app
uv run music-app
```

## Controls

| Key | Action |
|---|---|
| `Space` | Play / pause from playback cursor |
| `Left` / `Right` | Move active cursor left/right |
| `Up` / `Down` | Pitch up/down (also previews note sound) |
| `W` / `S` | Increase / decrease tempo |
| `Backspace` | Delete selected note |
| `Tab` | Switch selected note to opposite instrument at same/nearest beat |
| `T` | Cycle cursor focus: edit cursor 1 → edit cursor 2 → playback cursor |
| `K` | Cycle key signature and transpose notes |

### Supported note types

- `whole` (4.0 beats)
- `half` (2.0 beats)
- `quarter` (1.0 beat)
- `eighth` (0.5 beats)
- `sixteenth` (0.25 beats)

## Project Structure

```
music-app/
├── pyproject.toml                  # Project config & dependencies
├── data/                           # Instrument samples (one folder per note)
│   ├── instrument_c/c4.wav
│   ├── instrument_c_sharp/c_sharp4.wav
│   ├── instrument_d/d4.wav
│   └── ...
├── examples/
│   └── c_major_scale.json          # Pre-built C major scale
└── src/music_app/
    ├── main.py                     # Entry point
    ├── app.py                      # Main window (QMainWindow)
    ├── staff_widget.py             # Treble clef rendering (QPainter)
    ├── audio_engine.py             # Sample loading & playback (pygame)
    ├── models.py                   # Note & Sequence data models
    ├── commands.py                 # SequenceEditor command interface
    └── generate_samples.py         # Sine wave sample generator
```

## Replacing Instrument Samples

The generated sine-wave samples are placeholders. To use your own instrument:

1. Put your **MP3** or **WAV** files in the appropriate `data/instrument_*` folder
2. Name them following the convention: `c4.mp3`, `d4.wav`, `c_sharp4.mp3`, etc.
3. The audio engine auto-detects `.wav`, `.mp3`, and `.ogg` formats

## Choosing instrument folder per note in JSON

Each note can now include an optional `sample_bank` field to explicitly select
which folder under `data/` should be used for playback.

- `instrument` (int): staff lane / visual instrument (0 or 1)
- `sample_bank` (string, optional): exact folder name under `data/`

Example note entries:

```json
{
  "pitch": "C4",
  "duration": 1.0,
  "beat": 0.0,
  "note_type": "quarter",
  "instrument": 0,
  "sample_bank": "instrument_3"
}
```

```json
{
  "pitch": "G4",
  "duration": 1.0,
  "beat": 1.0,
  "note_type": "quarter",
  "instrument": 1,
  "sample_bank": "instrument_pad"
}
```

Behavior rules:

1. If `sample_bank` is set and that folder exists (e.g. `data/instrument_3/`),
   playback uses that bank first.
2. If `sample_bank` is missing or invalid, playback falls back to `instrument`
   index routing (`instrument` 0 -> `instrument_1`, `instrument` 1 -> `instrument_2`).
3. Existing JSON without `sample_bank` continues to work.

## Backend Integration

The `SequenceEditor` class in `commands.py` provides a simple string-based command API:

```python
from music_app.commands import SequenceEditor
from music_app.models import Sequence

seq = Sequence.from_file("examples/c_major_scale.json")
editor = SequenceEditor(seq)

editor.execute("move_right")   # Move cursor to next note
editor.execute("pitch_up")     # Shift selected note up one semitone
editor.execute("pitch_down")   # Shift selected note down one semitone
editor.execute("move_left")    # Move cursor to previous note
editor.execute("delete_note")  # Delete selected note
editor.execute("add_note")     # Insert a new C4 quarter note after cursor
```

## Dependencies

- **PyQt6** — GUI framework
- **pygame** — Audio playback
- **numpy** — Sample generation
- **scipy** — WAV file I/O
