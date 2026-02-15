"""Speech-to-server pipeline.

Records audio (or reads from a file), transcribes it with ElevenLabs STT,
and POSTs the transcription text to the MuseAid server's /speech endpoint
so that Gemini can edit the composition.

Usage::

    # From a file:
    python speech_to_server.py path/to/audio.mp3

    # From a URL:
    python speech_to_server.py --url https://example.com/audio.mp3

    # Interactive prompt (type the instruction directly, skip STT):
    python speech_to_server.py --text "add a C major scale"

Environment variables:
    ELEVENLABS_API_KEY  — ElevenLabs API key (required for STT mode)
    MUSEAID_SERVER_URL  — Server base URL (default: http://localhost:8000)
"""

from __future__ import annotations

import argparse
import os
import sys
from io import BytesIO
from pathlib import Path

import requests

# ── Server URL ───────────────────────────────────────────────────────

SERVER_URL = os.environ.get("MUSEAID_SERVER_URL", "http://localhost:8000")


def transcribe_file(file_path: str) -> str:
    """Transcribe a local audio file using ElevenLabs STT."""
    from dotenv import load_dotenv
    from elevenlabs.client import ElevenLabs

    load_dotenv()
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

    audio_data = Path(file_path).read_bytes()
    transcription = client.speech_to_text.convert(
        file=BytesIO(audio_data),
        model_id="scribe_v2",
        language_code="eng",
    )
    return transcription.text


def transcribe_url(audio_url: str) -> str:
    """Download audio from a URL and transcribe with ElevenLabs STT."""
    from dotenv import load_dotenv
    from elevenlabs.client import ElevenLabs

    load_dotenv()
    client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

    response = requests.get(audio_url, timeout=30)
    response.raise_for_status()

    transcription = client.speech_to_text.convert(
        file=BytesIO(response.content),
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
    group.add_argument("file", nargs="?", help="Path to a local audio file")
    group.add_argument("--url", help="URL of an audio file to transcribe")
    group.add_argument(
        "--text",
        help="Skip STT — send this text directly as the instruction",
    )
    args = parser.parse_args()

    # ── Get the instruction text ─────────────────────────────────
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
    else:
        parser.print_help()
        sys.exit(1)

    # ── Send to server ───────────────────────────────────────────
    print(f"Sending to server at {SERVER_URL}/speech …")
    result = send_to_server(text)
    print(f"Server response: {result}")


if __name__ == "__main__":
    main()
