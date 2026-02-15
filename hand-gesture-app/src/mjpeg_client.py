"""MJPEG HTTP client for multipart camera streams.

This reader keeps a persistent HTTP connection open and extracts JPEG frames
from a multipart/x-mixed-replace stream. It is intended for camera endpoints
like a Raspberry Pi MJPEG URL.
"""

from __future__ import annotations

import time
from typing import Tuple

import cv2
import httpx
import numpy as np


def probe_content_type(url: str, timeout: float = 2.0) -> tuple[int, str]:
    """Return (status_code, content_type) for an HTTP stream URL."""
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        with client.stream("GET", url) as response:
            return response.status_code, response.headers.get("content-type", "")


class MJPEGClient:
    """Persistent multipart MJPEG reader.

    Frames are extracted by scanning for JPEG SOI/EOI markers in the byte
    stream, which works across most MJPEG implementations.
    """

    def __init__(self, url: str, timeout: float = 5.0, read_chunk_size: int = 8192) -> None:
        self.url = url
        self._client = httpx.Client(timeout=timeout, follow_redirects=True)
        self._stream_cm = self._client.stream("GET", self.url)
        self._response = self._stream_cm.__enter__()
        self.content_type = self._response.headers.get("content-type", "")

        if self._response.status_code != 200:
            raise RuntimeError(f"MJPEG endpoint returned HTTP {self._response.status_code}")

        self._iter_bytes = self._response.iter_bytes(chunk_size=read_chunk_size)
        self._buffer = bytearray()
        self._closed = False

    @staticmethod
    def is_mjpeg_content_type(content_type: str | None) -> bool:
        if not content_type:
            return False
        ct = content_type.lower()
        return (
            "multipart/x-mixed-replace" in ct
            or "multipart/mixed" in ct
            or "motion-jpeg" in ct
            or "mjpeg" in ct
        )

    def is_opened(self) -> bool:
        return not self._closed

    def read(self) -> Tuple[bool, np.ndarray | None]:
        """Return one frame from the stream as (ret, frame)."""
        if self._closed:
            return False, None

        # Keep bounded memory in case of malformed stream data.
        max_buffer = 2_000_000
        deadline = time.monotonic() + 2.0

        while time.monotonic() < deadline:
            start = self._buffer.find(b"\xff\xd8")
            if start != -1:
                end = self._buffer.find(b"\xff\xd9", start + 2)
                if end != -1:
                    jpeg_bytes = bytes(self._buffer[start : end + 2])
                    del self._buffer[: end + 2]

                    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
                    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                    if img is not None:
                        return True, img

            try:
                chunk = next(self._iter_bytes)
            except StopIteration:
                return False, None
            except Exception:
                return False, None

            if not chunk:
                continue

            self._buffer.extend(chunk)
            if len(self._buffer) > max_buffer:
                # Keep the newest bytes only.
                self._buffer = self._buffer[-max_buffer:]

        return False, None

    def release(self) -> None:
        if self._closed:
            return

        self._closed = True
        try:
            self._stream_cm.__exit__(None, None, None)
        except Exception:
            pass
        try:
            self._client.close()
        except Exception:
            pass

