"""
Gesture classifier.

Uses the finger-state utility and the motion history buffer to detect the
five supported gestures.  Each detector method returns a ``(gesture_name,
confidence)`` tuple or ``None``.

Detection overview
------------------
* **Swipe gestures** (Pitch Up / Down):
  Analyse the displacement of the index fingertip over a sliding window.
  Require that only the index finger is extended and that the motion is
  predominantly vertical.

* **Open-palm swipe** (Scroll Forward / Backward):
  Analyse the horizontal displacement of the palm centre over a sliding
  window.  Require that 4+ fingers are extended (open palm) and that the
  motion is predominantly horizontal.

* **Pinch** (Toggle Playback):
  Detect the thumb and index finger tapping together.  Fires on the
  transition from fingers apart to fingers touching.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from src.config import (
    GESTURE_COOLDOWN_S,
    GESTURE_PITCH_DOWN,
    GESTURE_PITCH_UP,
    GESTURE_SCROLL_BACKWARD,
    GESTURE_SCROLL_FORWARD,
    GESTURE_SWITCH_STAFF,
    GESTURE_TOGGLE_PLAYBACK,
    INDEX_TIP,
    MIN_FRAMES_FOR_DETECTION,
    PALM_SWIPE_DIRECTIONALITY_RATIO,
    PALM_SWIPE_FRAME_WINDOW,
    PALM_SWIPE_MIN_DISPLACEMENT,
    PEACE_SIGN_FRAME_WINDOW,
    PEACE_SIGN_MIN_HOLD_FRAMES,
    PINCH_DISTANCE_THRESHOLD,
    PINCH_FRAME_WINDOW,
    PINCH_OPEN_THRESHOLD,
    SWIPE_DIRECTIONALITY_RATIO,
    SWIPE_FRAME_WINDOW,
    SWIPE_MIN_DISPLACEMENT,
    THUMB_TIP,
)
from src.finger_state import FingerState
from src.motion_buffer import MotionBuffer


@dataclass
class GestureEvent:
    """A single recognised gesture."""

    gesture: str
    confidence: float
    timestamp: float


class GestureDetector:
    """Stateful gesture detector that operates on a :class:`MotionBuffer`."""

    def __init__(self) -> None:
        # Cooldown tracking: gesture_name -> last-fire timestamp.
        self._cooldowns: dict[str, float] = {}
        # Pinch state: True when the thumb and index were apart (open) in a
        # recent frame.  A pinch only fires on the transition from open -> closed.
        self._pinch_was_open: bool = False
        # Peace-sign state: True when the hand was NOT showing a peace sign
        # recently.  The gesture fires on the transition from inactive -> active,
        # preventing repeated firing while the pose is held.
        self._peace_was_inactive: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        buffer: MotionBuffer,
        finger_state: FingerState,
    ) -> GestureEvent | None:
        """Analyse the current buffer and return a gesture event, or None.

        Checks are ordered from most specific to least specific so that
        ambiguous motions are resolved deterministically.
        """
        if len(buffer) < MIN_FRAMES_FOR_DETECTION:
            return None

        # Try each detector in priority order.
        detectors = [
            self._detect_palm_swipe,   # most specific: requires open palm
            self._detect_pinch,        # thumb-index tap (toggle playback)
            self._detect_peace_sign,   # peace sign (switch edit staff)
            self._detect_swipe,        # least specific: index-only + displacement
        ]
        for detector in detectors:
            result = detector(buffer, finger_state)
            if result is not None:
                gesture, confidence = result
                if self._on_cooldown(gesture):
                    continue
                self._fire(gesture)
                return GestureEvent(
                    gesture=gesture,
                    confidence=confidence,
                    timestamp=time.time(),
                )
        return None

    # ------------------------------------------------------------------
    # Cooldown helpers
    # ------------------------------------------------------------------

    def _on_cooldown(self, gesture: str) -> bool:
        last = self._cooldowns.get(gesture, 0.0)
        return (time.time() - last) < GESTURE_COOLDOWN_S

    def _fire(self, gesture: str) -> None:
        self._cooldowns[gesture] = time.time()

    # ------------------------------------------------------------------
    # Swipe detection (Pitch Up / Down)
    # ------------------------------------------------------------------

    def _detect_swipe(
        self,
        buffer: MotionBuffer,
        finger_state: FingerState,
    ) -> tuple[str, float] | None:
        """Detect a directional index-finger vertical swipe."""
        if not finger_state.only_index:
            return None

        positions = buffer.landmark_positions(INDEX_TIP, SWIPE_FRAME_WINDOW)
        if positions is None:
            return None

        # Displacement from first to last frame (x, y only).
        start = positions[0, :2]
        end = positions[-1, :2]
        dx = end[0] - start[0]
        dy = end[1] - start[1]

        abs_dx = abs(dx)
        abs_dy = abs(dy)

        # --- Vertical swipe (Pitch Up / Down) ---
        if abs_dy >= SWIPE_MIN_DISPLACEMENT:
            if abs_dx > 1e-6 and abs_dy / abs_dx < SWIPE_DIRECTIONALITY_RATIO:
                return None  # too diagonal
            # In normalised coords, y increases downward.
            # Negative dy = hand moved up on screen = "swipe up".
            confidence = min(1.0, abs_dy / (SWIPE_MIN_DISPLACEMENT * 2))
            if dy < 0:
                return (GESTURE_PITCH_UP, confidence)
            else:
                return (GESTURE_PITCH_DOWN, confidence)

        return None

    # ------------------------------------------------------------------
    # Open-palm swipe detection (Scroll Forward / Backward)
    # ------------------------------------------------------------------

    def _detect_palm_swipe(
        self,
        buffer: MotionBuffer,
        finger_state: FingerState,
    ) -> tuple[str, float] | None:
        """Detect an open-palm horizontal swipe for track scrolling."""
        if not finger_state.open_palm:
            return None

        # Use the palm centre (wrist + middle MCP midpoint) trajectory
        # instead of a single fingertip -- more stable for an open hand.
        positions = buffer.palm_centre_positions(PALM_SWIPE_FRAME_WINDOW)
        if positions is None:
            return None

        start = positions[0]
        end = positions[-1]
        dx = end[0] - start[0]
        dy = end[1] - start[1]

        abs_dx = abs(dx)
        abs_dy = abs(dy)

        if abs_dx < PALM_SWIPE_MIN_DISPLACEMENT:
            return None
        if abs_dy > 1e-6 and abs_dx / abs_dy < PALM_SWIPE_DIRECTIONALITY_RATIO:
            return None  # too diagonal

        confidence = min(1.0, abs_dx / (PALM_SWIPE_MIN_DISPLACEMENT * 2))

        # Frame is mirrored: dx < 0 in normalised coords = user swiped left.
        # User swipe left = scroll forward through the track.
        if dx < 0:
            return (GESTURE_SCROLL_FORWARD, confidence)
        else:
            return (GESTURE_SCROLL_BACKWARD, confidence)

    # ------------------------------------------------------------------
    # Peace-sign detection (Switch Staff / edit mode toggle)
    # ------------------------------------------------------------------

    def _detect_peace_sign(
        self,
        buffer: MotionBuffer,
        finger_state: FingerState,
    ) -> tuple[str, float] | None:
        """Detect a peace-sign (V) pose for switching the active edit staff.

        The gesture fires on the *transition* from a non-peace-sign hand
        state to a stable peace-sign pose.  This prevents repeated firing
        while the user holds the pose.
        """
        if not finger_state.peace_sign:
            # Hand is not currently showing a peace sign – reset the gate
            # so the next peace sign will fire.
            self._peace_was_inactive = True
            return None

        # Already fired for the current peace-sign hold – wait for reset.
        if not self._peace_was_inactive:
            return None

        # Require the peace sign to be stable for several consecutive frames
        # to avoid misfires from transient finger positions.
        frames = buffer.recent(PEACE_SIGN_FRAME_WINDOW)
        if len(frames) < PEACE_SIGN_MIN_HOLD_FRAMES:
            return None

        recent = frames[-PEACE_SIGN_MIN_HOLD_FRAMES:]
        peace_count = sum(1 for f in recent if f.finger_state.peace_sign)
        if peace_count < PEACE_SIGN_MIN_HOLD_FRAMES:
            return None

        # Transition confirmed – fire and latch.
        self._peace_was_inactive = False
        confidence = min(1.0, peace_count / len(recent))
        return (GESTURE_SWITCH_STAFF, confidence)

    # ------------------------------------------------------------------
    # Pinch detection (thumb-index tap for Toggle Playback)
    # ------------------------------------------------------------------

    def _detect_pinch(
        self,
        buffer: MotionBuffer,
        finger_state: FingerState,
    ) -> tuple[str, float] | None:
        """Detect a thumb-index pinch (tapping thumb and index finger together).

        The gesture fires on the *transition* from open (fingers apart) to
        closed (fingers touching).  This prevents repeated firing while the
        fingers remain pinched.
        """
        thumb_positions = buffer.landmark_positions(THUMB_TIP, PINCH_FRAME_WINDOW)
        index_positions = buffer.landmark_positions(INDEX_TIP, PINCH_FRAME_WINDOW)
        if thumb_positions is None or index_positions is None:
            return None

        # Compute Euclidean distance between thumb tip and index tip for each
        # frame in the window (using x, y only -- z is too noisy).
        distances = np.linalg.norm(
            thumb_positions[:, :2] - index_positions[:, :2], axis=1
        )

        current_dist = float(distances[-1])
        max_dist = float(distances.max())

        # Update open/closed state.
        if max_dist >= PINCH_OPEN_THRESHOLD:
            self._pinch_was_open = True

        # Fire only on the transition: fingers were apart, now they are close.
        if current_dist < PINCH_DISTANCE_THRESHOLD and self._pinch_was_open:
            self._pinch_was_open = False
            # Confidence: closer pinch = higher confidence.
            confidence = min(1.0, (PINCH_DISTANCE_THRESHOLD - current_dist)
                             / PINCH_DISTANCE_THRESHOLD + 0.5)
            confidence = min(1.0, confidence)
            return (GESTURE_TOGGLE_PLAYBACK, confidence)

        return None
