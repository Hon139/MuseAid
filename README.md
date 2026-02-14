# Overview

MuseAid: hand gestures + speech + composition app. The **MuseAid server** coordinates everything; the **Composition App** (PyQt) connects via WebSocket; the **hand-gesture app** sends gestures via HTTP; **speech-to-text** is used on demand (file/URL or `--text`).

# Usage

# Local Development & Deployment

```bash
cp template.env .env   # then fill in ELEVEN_LABS_API_KEY for speech-to-text
```

## Running everything

Use **3 terminals** (or run the server and hand-gesture app in the background). Start the server first so the Composition App and hand-gesture app can connect.

### 1. MuseAid server (webserver)

Must be running before the Composition App and hand-gesture app.

```bash
cd server
uv sync
uv run uvicorn museaid_server.main:app --reload --host 0.0.0.0 --port 8000
```

Leave this running. The Composition App connects to `ws://localhost:8000/ws`; the hand-gesture app POSTs to `http://localhost:8000/gestures`.

### 2. Composition App (music editor + playback)

```bash
cd Composition_App
uv sync
# Optional: generate WAV samples if data/ is empty
# uv run generate-samples
uv run music-app
```

Press **Space** to play/stop. If the server is running, the status bar will show "Connected to MuseAid server" and gestures from the hand-gesture app will control the editor.

### 3. Hand-gesture app (webcam → gestures)

```bash
cd hand-gesture-app
uv sync
uv run python -m src.main
```

Press **q** to quit. Gestures are sent to the server and forwarded to the Composition App (e.g. pinch = toggle playback, index swipe = pitch up/down).

### 4. Speech-to-text (on demand)

Not a long-running service. Run when you want to send a spoken (or typed) instruction to Gemini to edit the composition. The server must be running, and the Composition App must be open (it receives the updated sequence via WebSocket).

```bash
cd ElevenL/py
# If you use a venv, activate it and install: requests, python-dotenv, elevenlabs

# Send text directly (no microphone/file):
python speech_to_server.py --text "add a C major scale"

# Transcribe from an audio file:
python speech_to_server.py path/to/recording.mp3

# Transcribe from a URL:
python speech_to_server.py --url https://example.com/audio.mp3
```

Set `ELEVENLABS_API_KEY` in your environment or in a `.env` in `ElevenL/py` (or project root) for file/URL transcription.







