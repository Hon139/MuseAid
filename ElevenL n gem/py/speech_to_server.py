"""Speech-to-server pipeline.

Records audio (or reads from a file/URL), transcribes it with ElevenLabs STT,
and POSTs the transcription text to the MuseAid server's /speech endpoint
so Gemini can edit the composition.

Usage::

    # From a file:
    python speech_to_server.py --file path/to/audio.mp3

    # From a URL:
    python speech_to_server.py --url https://example.com/audio.mp3

    # From microphone (press Enter to stop):
    python speech_to_server.py --mic

    # Direct text (skip STT):
    python speech_to_server.py --text "add a C major scale"

Environment variables:
    ELEVENLABS_API_KEY  — ElevenLabs API key (required for STT modes)
    MUSEAID_SERVER_URL  — Server base URL (default: http://localhost:8000)
"""

from __future__ import annotations

import argparse
import os
import sys
from io import BytesIO
from pathlib import Path
import wave

import numpy as np
import requests
from dotenv import load_dotenv

# ── Server URL ───────────────────────────────────────────────────────

SERVER_URL = os.environ.get("MUSEAID_SERVER_URL", "http://localhost:8000")


def _require_elevenlabs_api_key() -> str:
    """Return ElevenLabs API key or raise a clear error."""
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("Missing ELEVENLABS_API_KEY in environment/.env")
    return key


def _client():
    """Create ElevenLabs client with validated env configuration."""
    from elevenlabs.client import ElevenLabs

    load_dotenv()
    return ElevenLabs(api_key=_require_elevenlabs_api_key())


def _wav_bytes_from_float32_mono(samples: np.ndarray, sample_rate: int) -> bytes:
    """Encode float32 mono samples in [-1, 1] as a WAV byte payload."""
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)

    with BytesIO() as buffer:
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16
            wf.setframerate(sample_rate)
            wf.writeframes(pcm.tobytes())
        return buffer.getvalue()


def record_from_microphone(sample_rate: int = 16_000) -> bytes:
    """Record microphone audio until Enter is pressed; return WAV bytes."""
    try:
        import sounddevice as sd
    except Exception as exc:  # pragma: no cover - import depends on system audio stack
        raise RuntimeError("sounddevice is required for --mic mode") from exc

    print("Press Enter to start microphone recording...")
    input()

    chunks: list[np.ndarray] = []

    def _callback(indata, _frames, _time, status):
        if status:
            print(f"[mic] {status}", file=sys.stderr)
        chunks.append(indata.copy())

    print("Recording... press Enter to stop.")
    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        callback=_callback,
    ):
        input()

    if not chunks:
        raise RuntimeError("No audio captured from microphone")

    mono = np.concatenate(chunks, axis=0).reshape(-1)
    return _wav_bytes_from_float32_mono(mono, sample_rate)


def transcribe_file(file_path: str) -> str:
    """Transcribe a local audio file using ElevenLabs STT."""
    client = _client()

    audio_data = Path(file_path).read_bytes()
    transcription = client.speech_to_text.convert(
        file=BytesIO(audio_data),
        model_id="scribe_v2",
        language_code="eng",
    )
    return transcription.text


def transcribe_url(audio_url: str) -> str:
    """Download audio from a URL and transcribe with ElevenLabs STT."""
    client = _client()

    response = requests.get(audio_url, timeout=30)
    response.raise_for_status()

    transcription = client.speech_to_text.convert(
        file=BytesIO(response.content),
        model_id="scribe_v2",
        language_code="eng",
    )
    return transcription.text


def transcribe_wav_bytes(wav_bytes: bytes) -> str:
    """Transcribe in-memory WAV payload with ElevenLabs STT."""
    client = _client()
    transcription = client.speech_to_text.convert(
        file=BytesIO(wav_bytes),
        model_id="scribe_v2",
        language_code="eng",
    )
    return transcription.text


def send_to_server(text: str) -> dict:
    """POST the transcription text to the MuseAid server /speech endpoint."""
    resp = requests.post(
        f"{SERVER_URL}/speech",
        json={"text": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcribe speech and send to MuseAid server",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a local audio file")
    group.add_argument("--url", help="URL of an audio file to transcribe")
    group.add_argument(
        "--mic",
        action="store_true",
        help="Record from microphone until Enter is pressed, then transcribe",
    )
    group.add_argument(
        "--text",
        help="Skip STT — send this text directly as the instruction",
    )
    parser.add_argument(
        "--mic-sample-rate",
        type=int,
        default=16_000,
        help="Microphone recording sample rate in Hz (default: 16000)",
    )
    args = parser.parse_args()

    try:
        # ── Get the instruction text ─────────────────────────────
        if args.text:
            text = args.text
            print(f"Using direct text: {text!r}")
        elif args.url:
            print(f"Transcribing from URL: {args.url}")
            text = transcribe_url(args.url)
            print(f"Transcription: {text!r}")
        elif args.file:
            print(f"Transcribing file: {args.file}")
            text = transcribe_file(args.file)
            print(f"Transcription: {text!r}")
        elif args.mic:
            print("Recording from microphone...")
            wav_bytes = record_from_microphone(sample_rate=args.mic_sample_rate)
            text = transcribe_wav_bytes(wav_bytes)
            print(f"Transcription: {text!r}")
        else:
            parser.print_help()
            sys.exit(1)

        # ── Send to server ───────────────────────────────────────
        print(f"Sending to server at {SERVER_URL}/speech …")
        result = send_to_server(text)
        print(f"Server response: {result}")
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        print(f"HTTP error ({status}): {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
