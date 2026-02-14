# Music App

A music production app with treble clef staff notation display, built with PyQt6.

## Features

- **Treble clef staff** — Renders notes on a standard 5-line musical staff with a treble clef
- **Quarter note display** — Notes shown as filled noteheads with stems and proper staff positioning
- **Playback** — Press **Space** to play the sequence; notes highlight blue as they play
- **Example file** — Ships with a C major scale (C4→C5) pre-loaded
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

| Key   | Action                    |
|-------|---------------------------|
| Space | Play / Stop the sequence  |

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
