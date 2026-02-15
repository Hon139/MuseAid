"""
Entry point – webcam capture loop.

Wires together:
  HandTracker  ->  FingerState  ->  MotionBuffer  ->  GestureDetector
                                                   ->  Overlay
                                                   ->  JSON stdout + HTTP POST
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

import cv2
import httpx

from src.config import (
    CAMERA_HEIGHT,
    CAMERA_INDEX,
    CAMERA_SRC,
    CAMERA_WIDTH,
)
from src.ffmpeg_pipe import FFmpegPipe
from src.http_poller import HTTPPoller
from src.mjpeg_client import MJPEGClient, probe_content_type
from src.finger_state import get_finger_state
from src.gesture_detector import GestureDetector
from src.hand_tracker import HandTracker
from src.motion_buffer import MotionBuffer
from src.overlay import draw_overlay
from src.mjpeg_server import MJPEGServer

# How long (seconds) to keep showing the last gesture label on screen after
# it was detected, so the user has time to read it.
_GESTURE_DISPLAY_DURATION = 1.2

# MuseAid server URL — override with MUSEAID_SERVER_URL env var.
_SERVER_URL = os.environ.get("MUSEAID_SERVER_URL", "http://localhost:8000")


def _post_to_server(payload: dict) -> None:
    """Fire-and-forget POST to the MuseAid server (runs in a daemon thread)."""
    try:
        httpx.post(f"{_SERVER_URL}/gestures", json=payload, timeout=0.5)
    except Exception:
        # Don't crash the gesture loop if the server is unreachable.
        pass


def _emit_json(gesture: str, confidence: float, timestamp: float) -> None:
    """Write a JSON line to stdout and POST to the MuseAid server."""
    payload = {
        "gesture": gesture,
        "confidence": round(confidence, 3),
        "timestamp": round(timestamp, 3),
    }
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()

    # Non-blocking HTTP POST so the webcam loop is not delayed.
    t = threading.Thread(target=_post_to_server, args=(payload,), daemon=True)
    t.start()


def main() -> None:
    # Allow overriding camera source via CAMERA_SRC env var. If CAMERA_SRC
    # is not set we fall back to the integer CAMERA_INDEX for local devices.
    camera_src = CAMERA_INDEX
    if CAMERA_SRC is not None:
        # If the env var is a number, use int; otherwise pass the string
        # (useful for rtsp/http streams or device paths).
        try:
            camera_src = int(CAMERA_SRC)
        except Exception:
            camera_src = CAMERA_SRC

    cap = cv2.VideoCapture(camera_src)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    source = None  # one of: 'mjpeg', 'opencv', 'ffmpeg', 'http'
    ff = None
    http_poller = None
    mjpeg_client = None

    camera_src_is_http = isinstance(camera_src, str) and camera_src.lower().startswith(("http://", "https://"))
    probed_content_type = ""

    if camera_src_is_http:
        try:
            status_code, probed_content_type = probe_content_type(camera_src)
            print(
                f"Camera probe: url={camera_src} status={status_code} content-type={probed_content_type or 'unknown'}",
                file=sys.stderr,
            )
        except Exception as exc:
            print(f"Camera probe failed for {camera_src}: {exc}", file=sys.stderr)

    def _acquire_source() -> str | None:
        nonlocal cap, ff, http_poller, mjpeg_client

        # For HTTP MJPEG streams prefer the dedicated multipart reader first.
        if camera_src_is_http and MJPEGClient.is_mjpeg_content_type(probed_content_type):
            try:
                mjpeg_client = MJPEGClient(camera_src)
                if mjpeg_client.is_opened():
                    print("Camera backend selected: mjpeg", file=sys.stderr)
                    return "mjpeg"
            except Exception as exc:
                mjpeg_client = None
                print(f"MJPEG backend failed: {exc}", file=sys.stderr)

        # OpenCV capture (works for local webcams and some network streams).
        try:
            if cap is None:
                cap = cv2.VideoCapture(camera_src)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
            if cap.isOpened():
                print("Camera backend selected: opencv", file=sys.stderr)
                return "opencv"
        except Exception as exc:
            print(f"OpenCV backend failed: {exc}", file=sys.stderr)

        # FFmpeg rawpipe fallback (works for many stream protocols).
        try:
            ff = FFmpegPipe(camera_src, CAMERA_WIDTH, CAMERA_HEIGHT)
            if ff.is_opened():
                print("Camera backend selected: ffmpeg", file=sys.stderr)
                return "ffmpeg"
        except Exception as exc:
            ff = None
            print(f"FFmpeg backend failed: {exc}", file=sys.stderr)

        # HTTP single-image poller fallback.
        try:
            http_poller = HTTPPoller(camera_src)
            ok, _ = http_poller.read()
            if ok:
                print("Camera backend selected: http-poller", file=sys.stderr)
                return "http"
        except Exception as exc:
            http_poller = None
            print(f"HTTP poller backend failed: {exc}", file=sys.stderr)

        return None

    source = _acquire_source()

    if source is None:
        print(
            "ERROR: Cannot open camera source with any backend (mjpeg/opencv/ffmpeg/http).",
            file=sys.stderr,
        )
        print(f"Camera source: {camera_src}", file=sys.stderr)
        if probed_content_type:
            print(f"Probed content type: {probed_content_type}", file=sys.stderr)
        sys.exit(1)

    tracker = HandTracker()
    buffer = MotionBuffer()
    detector = GestureDetector()

    # For lingering gesture display.
    last_gesture_name: str | None = None
    last_gesture_time: float = 0.0

    # Determine whether we should show the OpenCV window. Containers on
    # Raspberry Pi are typically headless; set HEADLESS=1 to skip imshow().
    HEADLESS = os.environ.get("HEADLESS", "0") in ("1", "true", "True")

    print("Hand Gesture Recognition started. Press 'q' to quit.", file=sys.stderr)

    # Start the MJPEG web viewer when running headless or when explicitly
    # requested via ENABLE_MJPEG=1.  It serves the processed frames on
    # http://<host>:8080/ (container must be run with --network host).
    enable_mjpeg = os.environ.get("ENABLE_MJPEG", "0") in ("1", "true", "True")
    if HEADLESS and not enable_mjpeg:
        enable_mjpeg = True

    mjpeg_server = None
    if enable_mjpeg:
        mjpeg_port = int(os.environ.get("MJPEG_PORT", "8080"))
        try:
            mjpeg_server = MJPEGServer(port=mjpeg_port)
            mjpeg_server.start()
            print(f"MJPEG viewer available at http://0.0.0.0:{mjpeg_port}/", file=sys.stderr)
        except Exception as exc:
            mjpeg_server = None
            print(
                f"MJPEG viewer disabled: could not bind port {mjpeg_port} ({exc})",
                file=sys.stderr,
            )

    try:
        while True:
            if source == 'opencv':
                ret, frame = cap.read()
                if not ret:
                    # fall through to try other sources
                    source = None
                    # Skip processing this loop iteration if we didn't get a frame
                    time.sleep(0.01)
                    continue
            elif source == 'mjpeg':
                ret, frame = mjpeg_client.read()
                if not ret:
                    source = None
                    time.sleep(0.01)
                    continue
            elif source == 'ffmpeg':
                ret, frame = ff.read()
                if not ret:
                    source = None
                    # Skip processing this loop iteration if we didn't get a frame
                    time.sleep(0.01)
                    continue
            elif source == 'http':
                ret, frame = http_poller.read()
                if not ret:
                    source = None
                    # Skip processing this loop iteration if we didn't get a frame
                    time.sleep(0.01)
                    continue
            else:
                source = _acquire_source()
                if source is not None:
                    continue

                # Nothing available — wait briefly and retry
                time.sleep(0.5)
                continue

            # Mirror the frame so it feels natural (like a mirror).
            frame = cv2.flip(frame, 1)

            # --- Hand tracking ---
            result = tracker.process(frame)

            finger_state = None
            gesture_event = None
            mp_landmarks = None

            if result is not None:
                mp_landmarks = result.mp_landmarks
                finger_state = get_finger_state(result.landmarks_norm)

                # Push to motion buffer.
                buffer.push(result.landmarks_norm, finger_state)

                # --- Gesture detection ---
                gesture_event = detector.detect(buffer, finger_state)

                if gesture_event is not None:
                    _emit_json(
                        gesture_event.gesture,
                        gesture_event.confidence,
                        gesture_event.timestamp,
                    )
                    last_gesture_name = gesture_event.gesture
                    last_gesture_time = time.time()
            else:
                # No hand visible – clear the buffer so stale data doesn't
                # cause false positives when the hand reappears.
                buffer.clear()

            # Determine what gesture label to show on screen.
            display_name: str | None = None
            if gesture_event is not None:
                display_name = gesture_event.gesture
            elif (
                last_gesture_name is not None
                and (time.time() - last_gesture_time) < _GESTURE_DISPLAY_DURATION
            ):
                display_name = last_gesture_name

            # --- Overlay ---
            frame = draw_overlay(
                frame,
                mp_landmarks=mp_landmarks,
                finger_state=finger_state,
                gesture_event=gesture_event,
                buffer=buffer,
                gesture_display_name=display_name,
            )

            # Publish the frame to the MJPEG server if enabled.
            if mjpeg_server is not None:
                try:
                    mjpeg_server.publish(frame)
                except Exception:
                    pass

            if not HEADLESS:
                cv2.imshow("Hand Gesture Recognition", frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            else:
                # In headless mode don't call imshow/waitKey. Sleep briefly
                # so the loop does not spin at full CPU if frames are not
                # delivered continuously.
                time.sleep(0.01)
    finally:
        tracker.close()
        # Release any open sources.
        try:
            if mjpeg_client is not None:
                mjpeg_client.release()
        except Exception:
            pass
        try:
            if ff is not None:
                ff.release()
        except Exception:
            pass
        try:
            if http_poller is not None:
                http_poller.release()
        except Exception:
            pass
        try:
            if cap is not None and cap.isOpened():
                cap.release()
        except Exception:
            pass
        if mjpeg_server is not None:
            mjpeg_server.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
