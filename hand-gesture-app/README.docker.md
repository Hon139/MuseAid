# Docker & Raspberry Pi instructions for hand-gesture-app

This document explains how to build and run the `hand-gesture-app` inside Docker on a Raspberry Pi.

Two typical ways to provide camera frames to the container:

1. Device passthrough (recommended, simplest): give the container access to `/dev/video0`.
2. Network stream: run a lightweight streamer on the Pi host (e.g. `mjpg-streamer` or `raspivid`/`ffmpeg`) and set `CAMERA_SRC` to the stream URL.

Build
-----
On a Raspberry Pi (or using `buildx` for cross-build):

- Local build on Pi (recommended):

```bash
cd hand-gesture-app
docker build -t hand-gesture-app:pi .
```

- Cross-build from another machine (requires docker buildx):

```bash
cd hand-gesture-app
docker buildx build --platform linux/arm/v7 -t hand-gesture-app:pi --load .
```

Run (device passthrough)
------------------------
Give the container access to the Pi camera (or USB webcam) device node and use host networking so the app can reach the Composition app server running on the same Pi.

```bash
# If your MuseAid server runs on the same Pi on port 8000
docker run --rm \
  --device /dev/video0:/dev/video0 \
  --network host \
  -e HEADLESS=1 \
  -e MUSEAID_SERVER_URL=http://localhost:8000 \
  hand-gesture-app:pi
```

Notes:
- `HEADLESS=1` disables the OpenCV GUI (no X display needed). Keep this in containers.
- Using `--network host` makes `localhost:8000` inside container point to the Pi's local server.

Run (network stream)
---------------------
If you prefer to stream camera frames from the host (e.g. because you already run a streamer), set `CAMERA_SRC` to the stream URL.

Example using an MJPEG stream at `http://192.168.1.10:8080/video`:

```bash
docker run --rm \
  --network host \
  -e CAMERA_SRC="http://192.168.1.10:8080/video" \
  -e HEADLESS=1 \
  -e MUSEAID_SERVER_URL=http://localhost:8000 \
  hand-gesture-app:pi
```

Raspberry Pi MJPEG endpoint runbook (your setup)
-------------------------------------------------
For a Pi stream endpoint like `http://100.66.77.132:7123/`, use Docker Compose defaults in this repo.

The compose file is configured for Docker Desktop compatibility using bridge networking with explicit port mapping (`8090:8090`), so browser access works at `http://localhost:8090/`.

```bash
cd hand-gesture-app
docker compose up --build -d
```

The included `docker-compose.yml` is preconfigured with:
- `CAMERA_SRC=http://100.66.77.132:7123/`
- `HEADLESS=1`
- `ENABLE_MJPEG=1`
- `MJPEG_PORT=8080`
- `MUSEAID_SERVER_URL=http://localhost:8000`

What success looks like in logs:
- `Camera probe: url=http://100.66.77.132:7123/ status=200 content-type=multipart/...`
- `Camera backend selected: mjpeg`
- `MJPEG viewer available at http://0.0.0.0:8090/`

Quick validation checks:

```bash
# 1) Verify endpoint headers from host
curl -I http://100.66.77.132:7123/

# 2) Follow app logs
docker compose logs -f hand-gesture-app

# 3) Open processed preview stream
# http://localhost:8090/
```

If the MJPEG backend cannot open, the app falls back to OpenCV -> FFmpeg -> HTTP poller and logs each backend failure reason.

Troubleshooting
---------------
- MediaPipe on Raspberry Pi: the `mediapipe` pip wheel may not be available for your Pi OS/architecture. If `pip install mediapipe` fails during image build, consider one of:
  - Use a prebuilt wheel for your Pi (search for "mediapipe raspberry pi").
  - Install via `apt`/`apt-get` if available for your distribution.
  - Run the Python app outside Docker in a virtualenv where you can control binary dependencies more easily.

- Camera permission errors: ensure the user running Docker has permission to access `/dev/video0`. Using `sudo` to run Docker or adding the user to the `video` group helps.

- If you use `--device /dev/video0` and still don't get frames, check `v4l2-ctl --list-devices` on the host.

- Network MJPEG troubleshooting:
  - Confirm route/firewall from the Docker host to `100.66.77.132:7123`.
  - Confirm the endpoint returns multipart MJPEG headers (`content-type: multipart/x-mixed-replace` or similar).
  - If logs show backend fallback loops, inspect the first backend error line to identify whether the issue is HTTP reachability, stream format, or decoder failure.

Security
--------
Running containers with device access and host networking increases the attack surface; only run trusted images on trusted networks.

Next steps
----------
If you'd like, I can:
- Add a small systemd unit or docker-compose file for easy startup on boot.
- Attempt to detect the presence of a display and auto-toggle `HEADLESS`.
- Add a small health endpoint so the container reports readiness to the Composition app.
