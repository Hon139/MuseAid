"""Quick utility to test opening a camera source (env CAMERA_SRC) and
save a single frame to /tmp/frame.jpg. Useful when debugging VideoCapture
access from inside the Docker container.

Run inside the container like:
  CAMERA_SRC="http://100.66.77.132:7123/" python test_camera.py
"""
from __future__ import annotations

import os
import sys
import time

import cv2


def main() -> int:
    src = os.environ.get("CAMERA_SRC", "0")
    try:
        src_int = int(src)
        camera_src = src_int
    except Exception:
        camera_src = src

    print(f"Opening camera source: {camera_src}")

    cap = cv2.VideoCapture(camera_src)
    if not cap.isOpened():
        print("ERROR: cv2.VideoCapture failed to open the source.")
        return 2

    # Give the stream a short moment to warm up.
    time.sleep(0.5)

    for _ in range(5):
        ret, frame = cap.read()
        if ret and frame is not None:
            out_path = "/tmp/frame.jpg"
            cv2.imwrite(out_path, frame)
            print(f"Saved frame to {out_path}")
            cap.release()
            return 0
        time.sleep(0.2)

    print("ERROR: No frames received from the camera source.")
    cap.release()
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
