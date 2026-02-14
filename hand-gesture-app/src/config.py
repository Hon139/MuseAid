"""
Configuration constants for hand gesture recognition.

All tunable thresholds, cooldowns, buffer sizes, and gesture names live here
so they can be adjusted in one place without touching detection logic.
"""

# ---------------------------------------------------------------------------
# Gesture name constants (used in JSON output)
# ---------------------------------------------------------------------------
GESTURE_PITCH_UP = "PITCH_UP"
GESTURE_PITCH_DOWN = "PITCH_DOWN"
GESTURE_TOGGLE_PLAYBACK = "TOGGLE_PLAYBACK"
GESTURE_SCROLL_FORWARD = "SCROLL_FORWARD"
GESTURE_SCROLL_BACKWARD = "SCROLL_BACKWARD"
GESTURE_SWITCH_STAFF = "SWITCH_STAFF"

ALL_GESTURES = [
    GESTURE_PITCH_UP,
    GESTURE_PITCH_DOWN,
    GESTURE_TOGGLE_PLAYBACK,
    GESTURE_SCROLL_FORWARD,
    GESTURE_SCROLL_BACKWARD,
    GESTURE_SWITCH_STAFF,
]

# ---------------------------------------------------------------------------
# MediaPipe Hands configuration
# ---------------------------------------------------------------------------
MP_MAX_NUM_HANDS = 1
MP_MIN_DETECTION_CONFIDENCE = 0.7
MP_MIN_TRACKING_CONFIDENCE = 0.6

# ---------------------------------------------------------------------------
# Motion history buffer
# ---------------------------------------------------------------------------
# Number of frames to keep in the circular buffer.
# At ~30 fps this gives roughly 0.5-0.7 seconds of history.
BUFFER_SIZE = 20

# Minimum number of frames required in the buffer before gesture detection
# is attempted (avoids false positives on startup / hand re-entry).
MIN_FRAMES_FOR_DETECTION = 8

# ---------------------------------------------------------------------------
# Cooldown (seconds) – after a gesture fires, ignore the same gesture class
# for this duration to prevent duplicate detections.
# ---------------------------------------------------------------------------
GESTURE_COOLDOWN_S = 0.6

# ---------------------------------------------------------------------------
# Finger-state thresholds
# ---------------------------------------------------------------------------
# A finger is considered "extended" when the tip-to-MCP distance exceeds
# this fraction of the palm size (wrist-to-middle-MCP distance).
FINGER_EXTENDED_RATIO = 0.55

# For the thumb, we use a different heuristic (angle-based).
THUMB_EXTENDED_ANGLE_DEG = 40.0  # thumb tip angle threshold

# ---------------------------------------------------------------------------
# Swipe detection (Pitch Up / Down)
# ---------------------------------------------------------------------------
# Minimum displacement (in normalised landmark coords, 0-1 range) of the
# index fingertip over the analysis window to count as a swipe.
SWIPE_MIN_DISPLACEMENT = 0.12

# The ratio of primary-axis displacement to off-axis displacement must
# exceed this value to ensure the swipe is directional (not diagonal).
SWIPE_DIRECTIONALITY_RATIO = 1.8

# Number of recent frames to analyse for swipe velocity.
SWIPE_FRAME_WINDOW = 12

# ---------------------------------------------------------------------------
# Open-palm swipe detection (Scroll Forward / Backward)
# ---------------------------------------------------------------------------
# Minimum horizontal displacement (normalised coords) of the palm centre
# over the analysis window to count as a palm swipe.  Slightly lower than
# the index-finger swipe threshold because the palm centre is more stable.
PALM_SWIPE_MIN_DISPLACEMENT = 0.10

# Directionality ratio – primary (horizontal) vs off-axis (vertical)
# displacement must exceed this to ensure the motion is predominantly
# horizontal, not diagonal.
PALM_SWIPE_DIRECTIONALITY_RATIO = 1.8

# Number of recent frames to analyse for palm swipe.
PALM_SWIPE_FRAME_WINDOW = 12

# Minimum number of extended fingers to qualify as an "open palm".
PALM_SWIPE_MIN_FINGERS = 4

# ---------------------------------------------------------------------------
# Peace-sign detection (Switch Staff / edit mode toggle)
# ---------------------------------------------------------------------------
# Number of recent frames to analyse for peace-sign stability.
PEACE_SIGN_FRAME_WINDOW = 8

# Within the analysis window, the peace-sign pose must be present in at
# least this many frames to be considered stable (avoids misfires from
# transient finger positions).
PEACE_SIGN_MIN_HOLD_FRAMES = 4

# ---------------------------------------------------------------------------
# Pinch detection (thumb-index tap for Toggle Playback)
# ---------------------------------------------------------------------------
# Maximum normalised distance between thumb tip and index tip to count as a
# pinch (thumb and index finger touching).  In normalised coords (0-1 range).
PINCH_DISTANCE_THRESHOLD = 0.045

# The thumb and index must first be apart (distance > this value) before a
# pinch can be recognised.  Prevents repeated firing while fingers stay close.
PINCH_OPEN_THRESHOLD = 0.07

# Number of recent frames to analyse for the pinch gesture.
PINCH_FRAME_WINDOW = 8

# ---------------------------------------------------------------------------
# MediaPipe landmark indices (for readability)
# ---------------------------------------------------------------------------
WRIST = 0
THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_DIP = 7
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_DIP = 11
MIDDLE_TIP = 12
RING_MCP = 13
RING_PIP = 14
RING_DIP = 15
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20

# ---------------------------------------------------------------------------
# Landmark smoothing & outlier rejection
# ---------------------------------------------------------------------------
# Exponential moving average (EMA) smoothing factor for landmark positions.
# Lower values = heavier smoothing (more lag but less jitter).
# 1.0 = no smoothing, 0.3 = moderate smoothing.
# Raised from 0.45 to 0.55 to let gesture motion come through more clearly.
LANDMARK_SMOOTH_ALPHA = 0.55

# Maximum normalised-coordinate jump (Euclidean distance in x,y) allowed
# between consecutive frames.  Jumps larger than this are treated as
# tracking glitches and the new position is replaced with a prediction
# based on the previous velocity.
LANDMARK_MAX_JUMP = 0.18

# ---------------------------------------------------------------------------
# Overlay / visualisation
# ---------------------------------------------------------------------------
OVERLAY_FONT_SCALE = 1.2
OVERLAY_THICKNESS = 2
OVERLAY_GESTURE_COLOR = (0, 255, 0)       # green for gesture label
OVERLAY_FINGER_DEBUG_COLOR = (255, 200, 0) # cyan-ish for finger state
OVERLAY_TRAIL_COLOR = (0, 180, 255)        # orange trail
OVERLAY_TRAIL_MAX_POINTS = 30

# ---------------------------------------------------------------------------
# Webcam
# ---------------------------------------------------------------------------
CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
