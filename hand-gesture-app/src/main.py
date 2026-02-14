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
    CAMERA_WIDTH,
)
from src.finger_state import get_finger_state
from src.gesture_detector import GestureDetector
from src.hand_tracker import HandTracker
from src.motion_buffer import MotionBuffer
from src.overlay import draw_overlay

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
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    if not cap.isOpened():
        print("ERROR: Cannot open webcam.", file=sys.stderr)
        sys.exit(1)

    tracker = HandTracker()
    buffer = MotionBuffer()
    detector = GestureDetector()

    # For lingering gesture display.
    last_gesture_name: str | None = None
    last_gesture_time: float = 0.0

    print("Hand Gesture Recognition started. Press 'q' to quit.", file=sys.stderr)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

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

            cv2.imshow("Hand Gesture Recognition", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        tracker.close()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
