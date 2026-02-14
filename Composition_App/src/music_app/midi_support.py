"""MIDI import/export support for Sequence objects."""

from __future__ import annotations

from pathlib import Path

import mido

from .models import Note, NoteType, PITCH_ORDER, Sequence


_NOTE_TYPE_BY_BEATS: list[tuple[float, NoteType]] = [
    (4.0, NoteType.WHOLE),
    (2.0, NoteType.HALF),
    (1.0, NoteType.QUARTER),
    (0.5, NoteType.EIGHTH),
]


def _beats_to_note_type(beats: float) -> str:
    for value, nt in _NOTE_TYPE_BY_BEATS:
        if abs(beats - value) < 1e-6:
            return nt.value
    # fallback to closest supported visual note type
    closest = min(_NOTE_TYPE_BY_BEATS, key=lambda item: abs(item[0] - beats))[1]
    return closest.value


def _pitch_to_midi(pitch: str) -> int:
    # input like C4, D#5, etc.
    note = pitch[:-1]
    octave = int(pitch[-1])
    semitone_map = {
        "C": 0,
        "C#": 1,
        "D": 2,
        "D#": 3,
        "E": 4,
        "F": 5,
        "F#": 6,
        "G": 7,
        "G#": 8,
        "A": 9,
        "A#": 10,
        "B": 11,
    }
    return 12 * (octave + 1) + semitone_map[note]


def _midi_to_pitch(note_number: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (note_number // 12) - 1
    name = names[note_number % 12]
    return f"{name}{octave}"


def export_midi(sequence: Sequence, out_path: Path) -> None:
    """Export a Sequence to a MIDI file (format 1, 2 tracks/instruments)."""
    mid = mido.MidiFile(type=1)
    ticks_per_beat = mid.ticks_per_beat

    # tempo/meta track
    meta = mido.MidiTrack()
    mid.tracks.append(meta)
    meta.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(sequence.bpm), time=0))
    meta.append(
        mido.MetaMessage(
            "time_signature",
            numerator=sequence.time_sig_num,
            denominator=sequence.time_sig_den,
            clocks_per_click=24,
            notated_32nd_notes_per_beat=8,
            time=0,
        )
    )

    for inst in (0, 1):
        track = mido.MidiTrack()
        mid.tracks.append(track)

        # Program changes: 0=piano for inst0, 73=flute for inst1
        program = 0 if inst == 0 else 73
        track.append(mido.Message("program_change", program=program, channel=inst, time=0))

        events: list[tuple[int, mido.Message]] = []
        for note in sequence.notes:
            if note.instrument != inst or note.is_rest:
                continue
            pitch_num = _pitch_to_midi(note.pitch)
            start_tick = int(note.beat * ticks_per_beat)
            duration_tick = int(note.duration * ticks_per_beat)
            end_tick = start_tick + max(1, duration_tick)

            events.append((start_tick, mido.Message("note_on", note=pitch_num, velocity=96, channel=inst, time=0)))
            events.append((end_tick, mido.Message("note_off", note=pitch_num, velocity=0, channel=inst, time=0)))

        # Sort by absolute time, then ensure note_off processed before note_on on same tick
        events.sort(key=lambda item: (item[0], 0 if item[1].type == "note_off" else 1))

        last_tick = 0
        for abs_tick, msg in events:
            msg.time = abs_tick - last_tick
            track.append(msg)
            last_tick = abs_tick

    out_path.parent.mkdir(parents=True, exist_ok=True)
    mid.save(out_path)


def import_midi(path: Path, name: str | None = None) -> Sequence:
    """Import a MIDI file into a Sequence.

    - Uses track index 1 => instrument 0, track index 2 => instrument 1
    - Converts note durations to supported visual types (whole/half/quarter/eighth)
    """
    mid = mido.MidiFile(path)
    ticks_per_beat = mid.ticks_per_beat

    bpm = 120
    ts_num, ts_den = 4, 4
    if mid.tracks:
        for msg in mid.tracks[0]:
            if msg.type == "set_tempo":
                bpm = int(round(mido.tempo2bpm(msg.tempo)))
            elif msg.type == "time_signature":
                ts_num, ts_den = msg.numerator, msg.denominator

    notes: list[Note] = []

    # map: (instrument, pitch_num) -> start_tick
    active: dict[tuple[int, int], int] = {}

    for track_idx, track in enumerate(mid.tracks[1:], start=1):
        instrument = 0 if track_idx == 1 else 1
        abs_tick = 0
        for msg in track:
            abs_tick += msg.time
            if msg.type == "note_on" and msg.velocity > 0:
                active[(instrument, msg.note)] = abs_tick
            elif msg.type in ("note_off", "note_on") and (msg.type == "note_off" or msg.velocity == 0):
                key = (instrument, msg.note)
                start_tick = active.pop(key, None)
                if start_tick is None:
                    continue

                beat = start_tick / ticks_per_beat
                duration = max(0.25, (abs_tick - start_tick) / ticks_per_beat)
                pitch = _midi_to_pitch(msg.note)

                # Keep within app's supported pitch range
                if pitch not in PITCH_ORDER:
                    continue

                notes.append(
                    Note(
                        pitch=pitch,
                        duration=duration,
                        beat=beat,
                        note_type=_beats_to_note_type(duration),
                        instrument=instrument,
                    )
                )

    notes.sort(key=lambda n: (n.beat, n.instrument, n.pitch if n.pitch != "REST" else "ZZZ"))

    return Sequence(
        name=name or path.stem,
        bpm=bpm,
        time_sig_num=ts_num,
        time_sig_den=ts_den,
        key="C",
        notes=notes,
    )

