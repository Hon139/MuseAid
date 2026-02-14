"""
MediaPipe Hands wrapper (Tasks API, mediapipe >= 0.10).

Accepts a BGR frame from OpenCV, runs hand landmark detection, and returns
both the normalised landmarks (0-1) and pixel-space landmarks for the first
detected hand.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import mediapipe as mp
import numpy as np

from src.config import (
    MP_MAX_NUM_HANDS,
    MP_MIN_DETECTION_CONFIDENCE,
    MP_MIN_TRACKING_CONFIDENCE,
)

# Resolve the model path relative to this file so it works regardless of cwd.
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")

BaseOptions = mp.tasks.BaseOptions
HandLandmarker = mp.tasks.vision.HandLandmarker
HandLandmarkerOptions = mp.tasks.vision.HandLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode


@dataclass
class HandResult:
    """Container for a single hand detection result."""

    # (21, 3) array of normalised landmarks – x, y in [0, 1], z relative depth.
    landmarks_norm: np.ndarray

    # (21, 3) array of pixel-space landmarks – x, y in pixels, z unchanged.
    landmarks_px: np.ndarray

    # The raw list[NormalizedLandmark] from the Tasks API (useful for drawing).
    mp_landmarks: list

    # Handedness label ("Left" or "Right") and score.
    handedness: str
    handedness_score: float


class HandTracker:
    """Thin wrapper around MediaPipe HandLandmarker (Tasks API)."""

    def __init__(self) -> None:
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=_MODEL_PATH),
            num_hands=MP_MAX_NUM_HANDS,
            min_hand_detection_confidence=MP_MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=MP_MIN_TRACKING_CONFIDENCE,
            running_mode=RunningMode.VIDEO,
        )
        self._landmarker = HandLandmarker.create_from_options(options)
        self._frame_ts_ms: int = 0  # monotonic timestamp for VIDEO mode

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, bgr_frame: np.ndarray) -> Optional[HandResult]:
        """Run detection on a BGR frame.

        Returns a ``HandResult`` for the first detected hand, or ``None``
        if no hand is visible.
        """
        h, w, _ = bgr_frame.shape

        # Convert BGR -> RGB and wrap in a MediaPipe Image.
        rgb = bgr_frame[:, :, ::-1].copy()
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        # The VIDEO running mode requires a monotonically increasing timestamp.
        self._frame_ts_ms += 33  # ~30 fps
        result = self._landmarker.detect_for_video(mp_image, self._frame_ts_ms)

        if not result.hand_landmarks:
            return None

        mp_landmarks = result.hand_landmarks[0]  # list[NormalizedLandmark]

        # Build numpy arrays.
        norm = np.array(
            [(lm.x, lm.y, lm.z) for lm in mp_landmarks],
            dtype=np.float64,
        )
        px = norm.copy()
        px[:, 0] *= w
        px[:, 1] *= h
        # z stays as the relative depth value from MediaPipe.

        # Handedness
        hand_class = result.handedness[0][0]  # Category object
        handedness = hand_class.category_name
        handedness_score = hand_class.score

        return HandResult(
            landmarks_norm=norm,
            landmarks_px=px,
            mp_landmarks=mp_landmarks,
            handedness=handedness,
            handedness_score=handedness_score,
        )

    def close(self) -> None:
        """Release MediaPipe resources."""
        self._landmarker.close()
