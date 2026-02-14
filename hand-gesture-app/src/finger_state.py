"""
Finger-state utility.

Given the 21 MediaPipe hand landmarks (normalised), determine which of the
five fingers are currently *extended* (open) vs *curled* (closed).

The result is a simple dict mapping finger name to a boolean.

Detection approach
------------------
* **Thumb**: Compare the angle at the thumb IP joint.  If the thumb tip is
  far enough from the index MCP relative to the palm size, the thumb is open.
  We also check that the thumb tip is lateral to the thumb IP (accounts for
  left/right hand mirroring).
* **Index / Middle / Ring / Pinky**: A finger is extended when the distance
  from its *tip* to the *wrist* is greater than the distance from its *PIP*
  (proximal inter-phalangeal) joint to the wrist.  This is a simple and
  robust heuristic that works regardless of hand orientation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.config import (
    INDEX_DIP,
    INDEX_MCP,
    INDEX_PIP,
    INDEX_TIP,
    MIDDLE_DIP,
    MIDDLE_MCP,
    MIDDLE_PIP,
    MIDDLE_TIP,
    PINKY_DIP,
    PINKY_MCP,
    PINKY_PIP,
    PINKY_TIP,
    RING_DIP,
    RING_MCP,
    RING_PIP,
    RING_TIP,
    THUMB_CMC,
    THUMB_IP,
    THUMB_MCP,
    THUMB_TIP,
    WRIST,
)


@dataclass
class FingerState:
    """Boolean state for each finger."""

    thumb: bool
    index: bool
    middle: bool
    ring: bool
    pinky: bool

    def as_dict(self) -> dict[str, bool]:
        return {
            "thumb": self.thumb,
            "index": self.index,
            "middle": self.middle,
            "ring": self.ring,
            "pinky": self.pinky,
        }

    def count_extended(self) -> int:
        return sum([self.thumb, self.index, self.middle, self.ring, self.pinky])

    @property
    def only_index(self) -> bool:
        """True when *only* the index finger is extended (thumb may vary)."""
        return (
            self.index
            and not self.middle
            and not self.ring
            and not self.pinky
        )

    @property
    def open_palm(self) -> bool:
        """True when 4+ fingers are extended (flat open hand)."""
        return self.count_extended() >= 4


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance between two 2-D or 3-D points."""
    return float(np.linalg.norm(a - b))


def _angle_at(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle (degrees) at vertex *b* formed by segments b->a and b->c."""
    ba = a - b
    bc = c - b
    cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def get_finger_state(landmarks: np.ndarray) -> FingerState:
    """Determine which fingers are extended.

    Parameters
    ----------
    landmarks : np.ndarray
        Shape ``(21, 3)`` normalised landmark array (x, y, z).

    Returns
    -------
    FingerState
    """
    # Use only x, y for distance comparisons (z is relative depth and noisy).
    lm = landmarks[:, :2]

    # -- Four fingers (index, middle, ring, pinky) --------------------------
    # Primary: tip is farther from wrist than PIP.
    # Secondary: tip is farther from wrist than DIP (more lenient, catches
    # partially-extended fingers during rotation gestures).
    # We use the primary check, but fall back to the secondary if the primary
    # fails and the finger is "almost" extended (tip-to-wrist close to PIP).
    def _is_extended(tip: int, pip: int, dip: int, mcp: int) -> bool:
        tip_dist = _dist(lm[tip], lm[WRIST])
        pip_dist = _dist(lm[pip], lm[WRIST])
        dip_dist = _dist(lm[dip], lm[WRIST])
        mcp_dist = _dist(lm[mcp], lm[WRIST])
        # Primary: tip farther than PIP from wrist.
        if tip_dist > pip_dist:
            return True
        # Secondary: tip farther than DIP AND tip farther than MCP.
        # This catches fingers that are mostly straight but slightly curled
        # at the PIP (common for ring finger during rotation).
        if tip_dist > dip_dist and tip_dist > mcp_dist * 1.1:
            return True
        return False

    index = _is_extended(INDEX_TIP, INDEX_PIP, INDEX_DIP, INDEX_MCP)
    middle = _is_extended(MIDDLE_TIP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_MCP)
    ring = _is_extended(RING_TIP, RING_PIP, RING_DIP, RING_MCP)
    pinky = _is_extended(PINKY_TIP, PINKY_PIP, PINKY_DIP, PINKY_MCP)

    # -- Thumb --------------------------------------------------------------
    # The thumb is trickier because it moves laterally.  We check:
    #   1. The angle at the thumb IP joint is large enough (finger is straight).
    #   2. The thumb tip is farther from the palm centre than the thumb MCP.
    thumb_angle = _angle_at(
        landmarks[THUMB_MCP, :3],
        landmarks[THUMB_IP, :3],
        landmarks[THUMB_TIP, :3],
    )
    palm_centre = (lm[WRIST] + lm[MIDDLE_MCP]) / 2.0
    thumb_tip_dist = _dist(lm[THUMB_TIP], palm_centre)
    thumb_mcp_dist = _dist(lm[THUMB_MCP], palm_centre)
    thumb = thumb_angle > 150.0 and thumb_tip_dist > thumb_mcp_dist

    return FingerState(
        thumb=thumb,
        index=index,
        middle=middle,
        ring=ring,
        pinky=pinky,
    )
