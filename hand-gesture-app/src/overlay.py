"""
Visual overlay renderer (Tasks API, mediapipe >= 0.10).

Draws hand landmarks, gesture labels, finger-state debug info, and motion
trails onto the OpenCV frame for real-time feedback.
"""

from __future__ import annotations

import cv2
import mediapipe as mp
import numpy as np

from src.config import (
    INDEX_TIP,
    OVERLAY_FINGER_DEBUG_COLOR,
    OVERLAY_FONT_SCALE,
    OVERLAY_GESTURE_COLOR,
    OVERLAY_THICKNESS,
    OVERLAY_TRAIL_COLOR,
    OVERLAY_TRAIL_MAX_POINTS,
)
from src.finger_state import FingerState
from src.gesture_detector import GestureEvent
from src.motion_buffer import MotionBuffer

# New Tasks-API drawing utilities.
_drawing_utils = mp.tasks.vision.drawing_utils
_DrawingSpec = _drawing_utils.DrawingSpec
_HandConns = mp.tasks.vision.HandLandmarksConnections

# Customise the landmark drawing style.
_LANDMARK_STYLE = _DrawingSpec(color=(121, 22, 76), thickness=2, circle_radius=3)
_CONNECTION_STYLE = _DrawingSpec(color=(250, 44, 250), thickness=2)


def draw_overlay(
    frame: np.ndarray,
    mp_landmarks: list | None,
    finger_state: FingerState | None,
    gesture_event: GestureEvent | None,
    buffer: MotionBuffer,
    gesture_display_name: str | None = None,
) -> np.ndarray:
    """Draw all overlay elements onto *frame* (mutates in place and returns it).

    Parameters
    ----------
    frame : np.ndarray
        The BGR frame to draw on.
    mp_landmarks :
        The raw ``list[NormalizedLandmark]`` from the Tasks API (or ``None``).
    finger_state :
        Current ``FingerState`` (or ``None`` if no hand detected).
    gesture_event :
        The gesture event detected this frame (or ``None``).
    buffer :
        The motion buffer (used for drawing trails).
    gesture_display_name :
        If provided, show this string as the "active gesture" even when
        ``gesture_event`` is ``None`` (used for lingering display).
    """
    h, w, _ = frame.shape

    # 1. Hand landmarks & connections.
    if mp_landmarks is not None:
        _drawing_utils.draw_landmarks(
            frame,
            mp_landmarks,
            _HandConns.HAND_CONNECTIONS,
            _LANDMARK_STYLE,
            _CONNECTION_STYLE,
        )

    # 2. Gesture label (large, top-left).
    label = gesture_display_name or ""
    if gesture_event is not None:
        label = gesture_event.gesture
    if label:
        cv2.putText(
            frame,
            label,
            (20, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            OVERLAY_FONT_SCALE * 1.4,
            OVERLAY_GESTURE_COLOR,
            OVERLAY_THICKNESS + 1,
            cv2.LINE_AA,
        )

    # 3. Finger-state debug info (bottom-left).
    if finger_state is not None:
        state_str = "  ".join(
            f"{name}: {'UP' if val else '--'}"
            for name, val in finger_state.as_dict().items()
        )
        cv2.putText(
            frame,
            state_str,
            (20, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            OVERLAY_FONT_SCALE * 0.55,
            OVERLAY_FINGER_DEBUG_COLOR,
            1,
            cv2.LINE_AA,
        )

    # 4. Motion trail for the index fingertip.
    _draw_trail(frame, buffer, INDEX_TIP, w, h, OVERLAY_TRAIL_COLOR)

    # 5. If the palm is open, draw a palm-centre trail to give visual
    #    feedback during open-palm swipe gestures.
    if finger_state is not None and finger_state.open_palm:
        _draw_palm_centre_trail(frame, buffer, w, h, (0, 255, 180))

    return frame


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

# Number of interpolated sub-points between each pair of control points
# for Catmull-Rom spline rendering.  Higher = smoother but more draw calls.
_SPLINE_SUBDIVISIONS = 6


def _catmull_rom(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    n: int,
) -> list[tuple[int, int]]:
    """Return *n* interpolated points on the Catmull-Rom segment p1 -> p2.

    *p0* and *p3* are the neighbouring control points that influence the
    tangent at *p1* and *p2* respectively.
    """
    pts: list[tuple[int, int]] = []
    for i in range(n):
        t = i / n
        t2 = t * t
        t3 = t2 * t
        # Catmull-Rom basis (tension = 0.5)
        x = 0.5 * (
            (2.0 * p1[0])
            + (-p0[0] + p2[0]) * t
            + (2.0 * p0[0] - 5.0 * p1[0] + 4.0 * p2[0] - p3[0]) * t2
            + (-p0[0] + 3.0 * p1[0] - 3.0 * p2[0] + p3[0]) * t3
        )
        y = 0.5 * (
            (2.0 * p1[1])
            + (-p0[1] + p2[1]) * t
            + (2.0 * p0[1] - 5.0 * p1[1] + 4.0 * p2[1] - p3[1]) * t2
            + (-p0[1] + 3.0 * p1[1] - 3.0 * p2[1] + p3[1]) * t3
        )
        pts.append((int(round(x)), int(round(y))))
    return pts


def _interpolate_spline(
    points: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Expand a polyline into a smooth Catmull-Rom spline.

    Returns a denser list of pixel-coordinate points.  If there are fewer
    than 3 input points, returns the original list unchanged (not enough
    control points for a spline).
    """
    if len(points) < 3:
        return points

    result: list[tuple[int, int]] = []
    n = len(points)
    for i in range(n - 1):
        p0 = points[max(i - 1, 0)]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[min(i + 2, n - 1)]
        result.extend(_catmull_rom(p0, p1, p2, p3, _SPLINE_SUBDIVISIONS))
    # Always include the very last control point.
    result.append(points[-1])
    return result


def _draw_trail(
    frame: np.ndarray,
    buffer: MotionBuffer,
    landmark_id: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
) -> None:
    """Draw a fading, spline-smoothed polyline trail for a single landmark."""
    raw_points = buffer.trail_px(landmark_id, w, h, n=OVERLAY_TRAIL_MAX_POINTS)
    if len(raw_points) < 2:
        return
    points = _interpolate_spline(raw_points)
    for i in range(1, len(points)):
        alpha = i / len(points)  # 0 -> 1 (fades in)
        thickness = max(1, int(3 * alpha))
        c = tuple(int(v * alpha) for v in color)
        cv2.line(frame, points[i - 1], points[i], c, thickness, cv2.LINE_AA)


def _draw_palm_centre_trail(
    frame: np.ndarray,
    buffer: MotionBuffer,
    w: int,
    h: int,
    color: tuple[int, int, int],
) -> None:
    """Draw a spline-smoothed trail for the palm centre (wrist + middle MCP midpoint)."""
    frames = buffer.recent(OVERLAY_TRAIL_MAX_POINTS)
    if len(frames) < 2:
        return
    raw_points: list[tuple[int, int]] = []
    for f in frames:
        palm = f.landmarks_norm[[0, 9], :2]  # WRIST=0, MIDDLE_MCP=9
        cx = int(palm[:, 0].mean() * w)
        cy = int(palm[:, 1].mean() * h)
        raw_points.append((cx, cy))
    points = _interpolate_spline(raw_points)
    for i in range(1, len(points)):
        alpha = i / len(points)
        thickness = max(1, int(3 * alpha))
        c = tuple(int(v * alpha) for v in color)
        cv2.line(frame, points[i - 1], points[i], c, thickness, cv2.LINE_AA)
