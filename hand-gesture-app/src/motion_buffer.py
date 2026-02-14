"""
Circular buffer for hand-landmark motion history.

Stores per-frame snapshots of normalised landmarks together with their
timestamps so that the gesture detector can analyse trajectories, velocities,
and angular changes over a sliding window.

Includes two layers of temporal filtering applied on ``push()``:

1. **Outlier rejection** – if a landmark jumps farther than
   ``LANDMARK_MAX_JUMP`` (normalised coords) in a single frame, the raw
   position is replaced with a linear prediction from the previous two
   frames.  This catches the erratic "teleporting" that MediaPipe produces
   when the hand moves very fast.

2. **Exponential moving average (EMA)** – each landmark position is blended
   with the previous smoothed position using factor ``LANDMARK_SMOOTH_ALPHA``.
   This dampens high-frequency jitter while keeping the trail responsive.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from src.config import (
    BUFFER_SIZE,
    LANDMARK_MAX_JUMP,
    LANDMARK_SMOOTH_ALPHA,
    WRIST,
)
from src.finger_state import FingerState


@dataclass
class FrameSnapshot:
    """A single frame's worth of data stored in the buffer."""

    timestamp: float
    landmarks_norm: np.ndarray   # (21, 3)
    finger_state: FingerState


class MotionBuffer:
    """Fixed-size circular buffer of ``FrameSnapshot`` objects.

    Applies outlier rejection and EMA smoothing to landmark positions on
    every ``push()`` so that downstream consumers (gesture detection, trail
    drawing) see a clean trajectory even during fast hand motion.
    """

    def __init__(self, max_size: int = BUFFER_SIZE) -> None:
        self._buf: deque[FrameSnapshot] = deque(maxlen=max_size)
        # Last smoothed landmarks for EMA (None until first push).
        self._smooth: np.ndarray | None = None

    # ------------------------------------------------------------------
    # Writing
    # ------------------------------------------------------------------

    def push(
        self,
        landmarks_norm: np.ndarray,
        finger_state: FingerState,
        timestamp: float | None = None,
    ) -> None:
        """Append a new snapshot to the buffer.

        The raw *landmarks_norm* are first passed through outlier rejection
        and EMA smoothing before being stored.
        """
        if timestamp is None:
            timestamp = time.time()

        raw = landmarks_norm.copy()

        if self._smooth is not None:
            raw = self._reject_outliers(raw)
            smoothed = (
                LANDMARK_SMOOTH_ALPHA * raw
                + (1.0 - LANDMARK_SMOOTH_ALPHA) * self._smooth
            )
        else:
            smoothed = raw

        self._smooth = smoothed.copy()

        self._buf.append(
            FrameSnapshot(
                timestamp=timestamp,
                landmarks_norm=smoothed,
                finger_state=finger_state,
            )
        )

    def clear(self) -> None:
        self._buf.clear()
        self._smooth = None

    # ------------------------------------------------------------------
    # Outlier rejection
    # ------------------------------------------------------------------

    def _reject_outliers(self, raw: np.ndarray) -> np.ndarray:
        """Replace landmarks that jumped too far with a linear prediction.

        For each landmark, if the Euclidean distance (x, y) from the
        previous smoothed position exceeds ``LANDMARK_MAX_JUMP``, the raw
        value is replaced with a prediction extrapolated from the last two
        buffered positions (or simply the last smoothed position if only one
        previous frame exists).
        """
        assert self._smooth is not None
        prev = self._smooth

        # Per-landmark x,y distance from previous smoothed position.
        diffs = raw[:, :2] - prev[:, :2]
        dists = np.linalg.norm(diffs, axis=1)

        outlier_mask = dists > LANDMARK_MAX_JUMP
        if not outlier_mask.any():
            return raw

        # Build predictions: linear extrapolation from last two frames.
        if len(self._buf) >= 2:
            prev2 = self._buf[-2].landmarks_norm
            prev1 = self._buf[-1].landmarks_norm
            predicted = prev1 + (prev1 - prev2)  # constant-velocity model
        else:
            predicted = prev  # fall back to last known position

        result = raw.copy()
        result[outlier_mask] = predicted[outlier_mask]
        return result

    # ------------------------------------------------------------------
    # Reading helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._buf)

    @property
    def latest(self) -> FrameSnapshot | None:
        return self._buf[-1] if self._buf else None

    def recent(self, n: int) -> list[FrameSnapshot]:
        """Return the *n* most recent snapshots (oldest first)."""
        items = list(self._buf)
        return items[-n:]

    # ------------------------------------------------------------------
    # Trajectory helpers
    # ------------------------------------------------------------------

    def landmark_positions(
        self, landmark_id: int, n: int
    ) -> np.ndarray | None:
        """Return an (n, 3) array of a single landmark's positions over the
        last *n* frames.  Returns ``None`` if there are fewer than *n* frames.
        """
        frames = self.recent(n)
        if len(frames) < n:
            return None
        return np.array([f.landmarks_norm[landmark_id] for f in frames])

    def timestamps(self, n: int) -> np.ndarray | None:
        """Return an (n,) array of timestamps for the last *n* frames."""
        frames = self.recent(n)
        if len(frames) < n:
            return None
        return np.array([f.timestamp for f in frames])

    def centroid_positions(
        self, landmark_ids: list[int], n: int
    ) -> np.ndarray | None:
        """Return an (n, 3) array of the centroid of several landmarks over
        the last *n* frames.
        """
        frames = self.recent(n)
        if len(frames) < n:
            return None
        centroids = []
        for f in frames:
            pts = f.landmarks_norm[landmark_ids]
            centroids.append(pts.mean(axis=0))
        return np.array(centroids)

    def palm_centre_positions(self, n: int) -> np.ndarray | None:
        """Return (n, 2) array of the palm centre (midpoint of wrist and
        middle-finger MCP) x, y over the last *n* frames.
        """
        from src.config import MIDDLE_MCP

        frames = self.recent(n)
        if len(frames) < n:
            return None
        centres = []
        for f in frames:
            wrist = f.landmarks_norm[WRIST, :2]
            mid_mcp = f.landmarks_norm[MIDDLE_MCP, :2]
            centres.append((wrist + mid_mcp) / 2.0)
        return np.array(centres)

    # ------------------------------------------------------------------
    # Trail for visualisation
    # ------------------------------------------------------------------

    def trail_px(
        self, landmark_id: int, frame_w: int, frame_h: int, n: int = 30
    ) -> list[tuple[int, int]]:
        """Return a list of (x_px, y_px) tuples for drawing a motion trail."""
        frames = self.recent(n)
        points: list[tuple[int, int]] = []
        for f in frames:
            x = int(f.landmarks_norm[landmark_id, 0] * frame_w)
            y = int(f.landmarks_norm[landmark_id, 1] * frame_h)
            points.append((x, y))
        return points
