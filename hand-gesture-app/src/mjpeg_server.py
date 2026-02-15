"""Tiny MJPEG HTTP server to stream processed frames to a browser.

Usage:
    server = MJPEGServer(port=8080)
    server.start()
    server.publish(frame)  # publish BGR numpy array frames
    server.stop()

This uses only the Python standard library and OpenCV for JPEG encoding.
It binds to 0.0.0.0 so when the container runs with `--network host` you can
open http://<host>:8080/ in your browser to see the live overlay.
"""
from __future__ import annotations

import io
import threading
from http import server
from typing import Optional

import cv2
import numpy as np


class _FrameBuffer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: Optional[bytes] = None

    def set(self, jpeg_bytes: bytes) -> None:
        with self._lock:
            self._frame = jpeg_bytes

    def get(self) -> Optional[bytes]:
        with self._lock:
            return self._frame


class _Handler(server.BaseHTTPRequestHandler):
    buffer: _FrameBuffer = None  # type: ignore

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler uses camelCase
        if self.path != "/":
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        try:
            while True:
                frame = self.buffer.get()
                if frame is None:
                    # If no frame yet, wait briefly.
                    threading.Event().wait(0.05)
                    continue

                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                # small delay to yield
                threading.Event().wait(0.03)
        except BrokenPipeError:
            # Client disconnected
            return
        except Exception:
            return


class MJPEGServer:
    def __init__(self, port: int = 8080) -> None:
        self._port = int(port)
        self._buffer = _FrameBuffer()
        self._server: Optional[server.HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        handler = _Handler
        handler.buffer = self._buffer
        self._server = server.HTTPServer(("0.0.0.0", self._port), handler)

        def _serve() -> None:
            try:
                self._server.serve_forever()
            except Exception:
                pass

        self._thread = threading.Thread(target=_serve, daemon=True)
        self._thread.start()

    def publish(self, frame: np.ndarray) -> None:
        """Encode BGR numpy array to JPEG and store in buffer."""
        if frame is None:
            return
        # Encode to JPEG in-memory
        ret, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ret:
            return
        self._buffer.set(jpeg.tobytes())

    def stop(self) -> None:
        if self._server is not None:
            try:
                self._server.shutdown()
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=1.0)
