"""Simple HTTP JPEG poller for single-image endpoints.

When a camera endpoint returns a single JPEG image per request (not MJPEG
or RTSP), this class polls the URL and decodes the JPEG into a BGR frame.
"""
from __future__ import annotations

from typing import Tuple

import httpx
import numpy as np
import cv2


class HTTPPoller:
    def __init__(self, url: str, timeout: float = 2.0) -> None:
        self.url = url
        self._timeout = float(timeout)
        self._client = httpx.Client(timeout=self._timeout)

    def read(self) -> Tuple[bool, np.ndarray | None]:
        """Perform a GET and decode the returned bytes as JPEG.

        Returns (ret, frame).
        """
        try:
            r = self._client.get(self.url, follow_redirects=True)
        except Exception:
            return False, None

        if r.status_code != 200:
            return False, None

        data = r.content
        if not data:
            return False, None

        # Try to decode JPEG bytes
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return False, None
        return True, img

    def is_opened(self) -> bool:
        return True

    def release(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass
