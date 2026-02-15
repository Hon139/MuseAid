"""A tiny FFmpeg-based frame source used as a fallback when OpenCV's
VideoCapture cannot open a network stream.

It starts ffmpeg with image rawvideo output and reads raw frames from
stdout. Frames are returned as BGR numpy arrays matching the configured
width/height.

Requires `ffmpeg` to be available in PATH (the Dockerfile installs it).
"""
from __future__ import annotations

import subprocess
from typing import Tuple

import numpy as np


class FFmpegPipe:
    def __init__(self, src: str, width: int, height: int) -> None:
        self._src = src
        self._w = int(width)
        self._h = int(height)

        # Build ffmpeg command that decodes the input and writes raw BGR24
        # frames to stdout at the requested size.
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            src,
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-vf",
            f"scale={self._w}:{self._h}",
            "-",
        ]

        # Start ffmpeg; read stdout as binary stream.
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if self._proc.stdout is None:
            raise RuntimeError("Failed to open ffmpeg stdout")

        # Number of bytes per frame (BGR24)
        self._frame_bytes = self._w * self._h * 3

    def read(self) -> Tuple[bool, np.ndarray | None]:
        """Read one frame from the ffmpeg stdout.

        Returns (ret, frame) where ret is True on success and frame is a
        HxWx3 BGR numpy array.
        """
        assert self._proc.stdout is not None
        raw = self._proc.stdout.read(self._frame_bytes)
        if not raw or len(raw) != self._frame_bytes:
            return False, None

        frame = np.frombuffer(raw, dtype=np.uint8)
        frame = frame.reshape((self._h, self._w, 3))
        return True, frame

    def is_opened(self) -> bool:
        return self._proc.poll() is None

    def release(self) -> None:
        try:
            if self._proc.poll() is None:
                self._proc.kill()
        finally:
            # Drain stderr to avoid zombie pipes
            try:
                if self._proc.stderr is not None:
                    self._proc.stderr.read()
            except Exception:
                pass
