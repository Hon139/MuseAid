# Architecture & Technical Documentation

This document explains how the hand gesture recognition application works,
from the raw webcam frame all the way to a structured JSON gesture event.
It is intended for developers who want to understand, modify, or extend the
system.

---

## Table of Contents

1. [High-Level Pipeline](#1-high-level-pipeline)
2. [Module-by-Module Walkthrough](#2-module-by-module-walkthrough)
   - 2.1 [config.py -- Central Configuration](#21-configpy----central-configuration)
   - 2.2 [hand_tracker.py -- Hand Landmark Detection](#22-hand_trackerpy----hand-landmark-detection)
   - 2.3 [finger_state.py -- Finger Extension Detection](#23-finger_statepy----finger-extension-detection)
   - 2.4 [motion_buffer.py -- Temporal History](#24-motion_bufferpy----temporal-history)
   - 2.5 [gesture_detector.py -- Gesture Classification](#25-gesture_detectorpy----gesture-classification)
   - 2.6 [overlay.py -- Visual Feedback](#26-overlaypy----visual-feedback)
   - 2.7 [main.py -- Application Loop](#27-mainpy----application-loop)
3. [Gesture Detection Algorithms](#3-gesture-detection-algorithms)
   - 3.1 [Swipe Gestures (Pitch Up / Down)](#31-swipe-gestures-pitch-up--down)
   - 3.2 [Open-Palm Swipe (Scroll Forward / Backward)](#32-open-palm-swipe-scroll-forward--backward)
   - 3.3 [Pinch (Toggle Playback)](#33-pinch-toggle-playback)
4. [Coordinate Systems & Frame Mirroring](#4-coordinate-systems--frame-mirroring)
5. [Cooldown & Deduplication](#5-cooldown--deduplication)
6. [Confidence Scoring](#6-confidence-scoring)
7. [Output Format](#7-output-format)
8. [Tuning Guide](#8-tuning-guide)
9. [Extending the System](#9-extending-the-system)

---

## 1. High-Level Pipeline

Every webcam frame passes through the following stages:

```
Webcam frame (BGR)
      |
      v
  [cv2.flip]  -- mirror horizontally so the display feels natural
      |
      v
  HandTracker.process()
      |  Converts BGR -> RGB, wraps in mp.Image, calls
      |  HandLandmarker.detect_for_video().
      |  Returns HandResult (21 landmarks in normalised + pixel coords)
      |  or None if no hand is visible.
      |
      v
  get_finger_state()
      |  Analyses the 21 landmarks to determine which of the five
      |  fingers (thumb, index, middle, ring, pinky) are extended.
      |  Returns a FingerState dataclass.
      |
      v
  MotionBuffer.push()
      |  Stores the current frame's landmarks + finger state + timestamp
      |  into a fixed-size circular buffer (default 20 frames).
      |
      v
  GestureDetector.detect()
      |  Reads the buffer and finger state.  Runs three sub-detectors
      |  in priority order:
      |    1. _detect_palm_swipe  (open-palm horizontal swipe)
      |    2. _detect_pinch       (thumb-index tap)
      |    3. _detect_swipe       (index swipe up/down)
      |  The first match that is not on cooldown wins.
      |  Returns a GestureEvent or None.
      |
      +---> _emit_json()  -- writes {"gesture":..., "confidence":..., "timestamp":...}
      |                      to stdout as a single JSON line.
      |
      v
  draw_overlay()
      |  Draws hand landmarks, gesture label, finger-state debug bar,
      |  and motion trails onto the frame.
      |
      v
  cv2.imshow()  -- displays the annotated frame in a window.
```

When no hand is detected, the motion buffer is cleared so that stale
landmark data from a previous hand position does not cause false positives
when the hand re-enters the frame.

---

## 2. Module-by-Module Walkthrough

### 2.1 `config.py` -- Central Configuration

Every tunable constant lives in this single file.  Nothing is hard-coded
elsewhere.  The constants are grouped into sections:

| Section | Examples | Purpose |
|---|---|---|
| Gesture names | `GESTURE_PITCH_UP`, `ALL_GESTURES` | String constants used in JSON output and internal routing |
| MediaPipe config | `MP_MAX_NUM_HANDS`, `MP_MIN_DETECTION_CONFIDENCE` | Passed to the HandLandmarker at initialisation |
| Buffer settings | `BUFFER_SIZE`, `MIN_FRAMES_FOR_DETECTION` | Control how much temporal history is kept and how soon detection can start |
| Cooldown | `GESTURE_COOLDOWN_S` | Prevents the same gesture from firing repeatedly |
| Finger-state thresholds | `FINGER_EXTENDED_RATIO`, `THUMB_EXTENDED_ANGLE_DEG` | Tune how aggressively fingers are classified as extended |
| Swipe thresholds | `SWIPE_MIN_DISPLACEMENT`, `SWIPE_DIRECTIONALITY_RATIO`, `SWIPE_FRAME_WINDOW` | Control sensitivity and directionality of index-finger swipe gestures |
| Palm-swipe thresholds | `PALM_SWIPE_MIN_DISPLACEMENT`, `PALM_SWIPE_DIRECTIONALITY_RATIO`, `PALM_SWIPE_FRAME_WINDOW`, `PALM_SWIPE_MIN_FINGERS` | Control sensitivity of the open-palm swipe gesture |
| Pinch thresholds | `PINCH_DISTANCE_THRESHOLD`, `PINCH_OPEN_THRESHOLD`, `PINCH_FRAME_WINDOW` | Control sensitivity of the thumb-index pinch gesture |
| Landmark indices | `WRIST` through `PINKY_TIP` | Named constants (0-20) for MediaPipe's 21 hand landmarks |
| Overlay settings | `OVERLAY_FONT_SCALE`, `OVERLAY_TRAIL_COLOR`, etc. | Visual appearance of the debug overlay |
| Webcam settings | `CAMERA_INDEX`, `CAMERA_WIDTH`, `CAMERA_HEIGHT` | Which camera to open and at what resolution |

### 2.2 `hand_tracker.py` -- Hand Landmark Detection

**Class: `HandTracker`**

This module wraps the MediaPipe Tasks API (`mediapipe >= 0.10`).  On
construction it:

1. Locates the `hand_landmarker.task` model file (bundled in `src/`).
2. Creates a `HandLandmarker` in `VIDEO` running mode.  VIDEO mode (as
   opposed to IMAGE or LIVE_STREAM) requires a monotonically increasing
   timestamp, which the tracker synthesises by incrementing by 33 ms per
   frame (~30 fps).

**`process(bgr_frame)` method:**

1. Converts the BGR frame to RGB (MediaPipe requirement).
2. Wraps it in an `mp.Image`.
3. Calls `detect_for_video()` with the synthetic timestamp.
4. If no hand is found, returns `None`.
5. Otherwise, extracts the first hand's 21 landmarks into two numpy arrays:
   - `landmarks_norm`: shape `(21, 3)`, x and y in `[0, 1]`, z is relative
     depth from MediaPipe.
   - `landmarks_px`: same but x and y are multiplied by frame width/height
     to give pixel coordinates.
6. Also extracts handedness ("Left" / "Right") and its confidence score.
7. Returns everything in a `HandResult` dataclass.

**Dataclass: `HandResult`**

| Field | Type | Description |
|---|---|---|
| `landmarks_norm` | `np.ndarray (21,3)` | Normalised x, y, z |
| `landmarks_px` | `np.ndarray (21,3)` | Pixel-space x, y; z unchanged |
| `mp_landmarks` | `list[NormalizedLandmark]` | Raw MediaPipe objects (passed to drawing utils) |
| `handedness` | `str` | `"Left"` or `"Right"` |
| `handedness_score` | `float` | Confidence of the handedness classification |

### 2.3 `finger_state.py` -- Finger Extension Detection

**Function: `get_finger_state(landmarks) -> FingerState`**

Takes the `(21, 3)` normalised landmark array and returns a `FingerState`
dataclass with a boolean for each finger.

**Algorithm for index / middle / ring / pinky:**

A finger is considered *extended* when its **tip** is farther from the
**wrist** than its **PIP joint** (the middle knuckle).  The intuition is
simple: when you curl a finger, the tip moves closer to the wrist than the
PIP does; when you extend it, the tip is the farthest point.

```
Extended:                 Curled:
  TIP  (far from wrist)    PIP  (far from wrist)
   |                         |
  DIP                       DIP
   |                         |
  PIP                       TIP  (close to wrist)
   |                         |
  MCP                       MCP
```

Only the x and y coordinates are used (z is too noisy for this comparison).

**Algorithm for the thumb:**

The thumb moves laterally rather than curling toward the palm, so the
tip-vs-PIP heuristic does not work.  Instead, two conditions must both be
true:

1. The angle at the thumb IP joint (formed by MCP -> IP -> TIP) is greater
   than 150 degrees, meaning the thumb is relatively straight.
2. The thumb tip is farther from the palm centre (midpoint of wrist and
   middle-finger MCP) than the thumb MCP is.

**Dataclass: `FingerState`**

| Field | Type | Description |
|---|---|---|
| `thumb` | `bool` | Whether the thumb is extended |
| `index` | `bool` | Whether the index finger is extended |
| `middle` | `bool` | Whether the middle finger is extended |
| `ring` | `bool` | Whether the ring finger is extended |
| `pinky` | `bool` | Whether the pinky is extended |

Convenience properties:

- `only_index`: True when the index is extended and middle, ring, pinky are
  all curled (thumb is ignored because it naturally varies).
- `open_palm`: True when 4 or more fingers are extended (flat open hand).
- `count_extended()`: Total number of extended fingers (0-5).
- `as_dict()`: Returns `{"thumb": bool, "index": bool, ...}`.

### 2.4 `motion_buffer.py` -- Temporal History

**Class: `MotionBuffer`**

A fixed-size circular buffer (Python `collections.deque` with `maxlen`)
that stores one `FrameSnapshot` per frame.

**Dataclass: `FrameSnapshot`**

| Field | Type | Description |
|---|---|---|
| `timestamp` | `float` | `time.time()` when the frame was captured |
| `landmarks_norm` | `np.ndarray (21,3)` | Copy of the normalised landmarks |
| `finger_state` | `FingerState` | Finger state at this frame |

**Key methods:**

| Method | Returns | Description |
|---|---|---|
| `push(landmarks, finger_state, timestamp)` | -- | Appends a snapshot; oldest is evicted when full |
| `clear()` | -- | Empties the buffer (called when the hand disappears) |
| `recent(n)` | `list[FrameSnapshot]` | The *n* most recent snapshots, oldest first |
| `landmark_positions(id, n)` | `np.ndarray (n,3)` or `None` | Trajectory of a single landmark over *n* frames |
| `centroid_positions(ids, n)` | `np.ndarray (n,3)` or `None` | Trajectory of the centroid of several landmarks |
| `palm_centre_positions(n)` | `np.ndarray (n,2)` or `None` | Trajectory of the palm centre (wrist + middle MCP midpoint) |
| `timestamps(n)` | `np.ndarray (n,)` or `None` | Timestamps for the last *n* frames |
| `trail_px(id, w, h, n)` | `list[(int,int)]` | Pixel-space trail for overlay drawing |

All trajectory methods return `None` if the buffer has fewer than *n*
frames, which prevents gesture detection from running on insufficient data.

### 2.5 `gesture_detector.py` -- Gesture Classification

**Class: `GestureDetector`**

Stateful detector that maintains per-gesture cooldown timestamps.

**`detect(buffer, finger_state) -> GestureEvent | None`**

1. If the buffer has fewer than `MIN_FRAMES_FOR_DETECTION` (8) frames,
   returns `None` immediately.
2. Runs three sub-detectors in priority order:
   - `_detect_palm_swipe` (most specific -- requires open palm + horizontal
     displacement)
   - `_detect_pinch` (thumb-index tap -- toggle playback)
   - `_detect_swipe` (least specific -- requires index-only + vertical
     displacement)
3. The first detector that returns a match is checked against the cooldown.
   If on cooldown, the loop continues to the next detector.  If not, the
   gesture fires and a `GestureEvent` is returned.

The priority ordering matters: palm swipe is checked first because it is the
most constrained (4+ fingers extended + horizontal motion), so it will never
be confused with an index-finger gesture.  Pinch is checked before swipe
because a thumb-index tap might incidentally produce some vertical
displacement of the index finger.

**Dataclass: `GestureEvent`**

| Field | Type | Description |
|---|---|---|
| `gesture` | `str` | One of the `GESTURE_*` constants |
| `confidence` | `float` | 0.0 to 1.0 (see Section 6) |
| `timestamp` | `float` | `time.time()` when the gesture was recognised |

### 2.6 `overlay.py` -- Visual Feedback

**Function: `draw_overlay(frame, mp_landmarks, finger_state, gesture_event, buffer, gesture_display_name)`**

Draws five layers onto the frame (mutates in place):

1. **Hand landmarks & connections** -- Uses MediaPipe's
   `drawing_utils.draw_landmarks()` with the `HAND_CONNECTIONS` set.
   Landmarks are drawn as small magenta circles; connections as magenta
   lines.

2. **Gesture label** -- Large green text in the top-left corner.  Shows
   either the just-detected gesture or a "lingering" label from the
   previous detection (kept for 1.2 seconds so the user can read it).

3. **Finger-state debug bar** -- Small text at the bottom of the frame
   showing each finger as `UP` or `--`.  Example:
   `thumb: --  index: UP  middle: --  ring: --  pinky: --`

4. **Index fingertip trail** -- An orange fading polyline showing the
   recent path of landmark 8 (index tip).  Older segments are dimmer and
   thinner; newer segments are brighter and thicker.

5. **Palm-centre trail** -- A green fading polyline showing the palm
   centre (midpoint of wrist and middle-finger MCP).  Only drawn when
   `finger_state.open_palm` is true, providing visual feedback during
   open-palm swipe gestures.

### 2.7 `main.py` -- Application Loop

**Function: `main()`**

1. Opens the webcam at 1280x720 using `cv2.VideoCapture`.
2. Instantiates `HandTracker`, `MotionBuffer`, and `GestureDetector`.
3. Enters the frame loop:
   - Reads a frame; mirrors it with `cv2.flip(frame, 1)`.
   - Passes it to `HandTracker.process()`.
   - If a hand is found: computes finger state, pushes to buffer, runs
     gesture detection.
   - If no hand: clears the buffer.
   - If a gesture is detected: calls `_emit_json()` to write a JSON line
     to stdout.
   - Draws the overlay and displays the frame.
   - Exits on `q` keypress.
4. On exit (including exceptions), closes the tracker, releases the camera,
   and destroys all OpenCV windows via a `finally` block.

**Function: `_emit_json(gesture, confidence, timestamp)`**

Writes a single JSON line to stdout and flushes immediately.  Informational
messages (like the startup banner) go to stderr, so stdout can be piped
cleanly to a file or another process.

---

## 3. Gesture Detection Algorithms

### 3.1 Swipe Gestures (Pitch Up / Down)

**Precondition:** `finger_state.only_index` must be true (index extended,
middle/ring/pinky curled; thumb is ignored).

**Algorithm:**

1. Retrieve the last `SWIPE_FRAME_WINDOW` (12) positions of the index
   fingertip (landmark 8) from the motion buffer.
2. Compute the displacement vector from the first to the last position:
   `dx = end.x - start.x`, `dy = end.y - start.y`.
3. If `|dy| >= SWIPE_MIN_DISPLACEMENT` (0.12 in normalised coords):
   - Check directionality: `|dy| / |dx|` must exceed
     `SWIPE_DIRECTIONALITY_RATIO` (1.8) to ensure the motion is
     predominantly vertical, not diagonal.
   - If `dy < 0` (hand moved upward in image space): **PITCH_UP**.
   - If `dy > 0` (hand moved downward): **PITCH_DOWN**.

Only vertical swipes are recognised by this detector.  Horizontal swipes
use the open-palm detector described below.

### 3.2 Open-Palm Swipe (Scroll Forward / Backward)

**Precondition:** `finger_state.open_palm` must be true (4 or more fingers
extended -- a flat, open hand).

**Algorithm:**

1. Retrieve the last `PALM_SWIPE_FRAME_WINDOW` (12) positions of the
   **palm centre** (midpoint of wrist and middle-finger MCP) from the
   motion buffer.  The palm centre is used instead of a single fingertip
   because it is more stable when all fingers are extended.
2. Compute the displacement vector from the first to the last position:
   `dx = end.x - start.x`, `dy = end.y - start.y`.
3. If `|dx| >= PALM_SWIPE_MIN_DISPLACEMENT` (0.10 in normalised coords):
   - Check directionality: `|dx| / |dy|` must exceed
     `PALM_SWIPE_DIRECTIONALITY_RATIO` (1.8) to ensure the motion is
     predominantly horizontal, not diagonal.
   - If `dx < 0` (hand moved left in the mirrored frame, i.e. the user
     swiped left from their perspective): **SCROLL_FORWARD**.
   - If `dx > 0` (user swiped right): **SCROLL_BACKWARD**.

The direction mapping follows a natural scrolling metaphor: swiping left
moves forward through the track, swiping right moves backward.

### 3.3 Pinch (Toggle Playback)

**Precondition:** None -- the pinch gesture is detected purely from the
distance between the thumb tip and index fingertip, regardless of which
other fingers are extended.

**Algorithm:**

1. Retrieve the last `PINCH_FRAME_WINDOW` (8) positions of the thumb tip
   (landmark 4) and index fingertip (landmark 8) from the motion buffer.
2. Compute the Euclidean distance (x, y only) between thumb tip and index
   tip for each frame in the window.
3. Track an internal open/closed state:
   - If the maximum distance in the window exceeds `PINCH_OPEN_THRESHOLD`
     (0.07), the fingers are considered "open" (apart).
4. The gesture fires when **both** conditions are met:
   - The current distance is below `PINCH_DISTANCE_THRESHOLD` (0.045) --
     the thumb and index finger are touching.
   - The fingers were previously "open" -- this ensures the gesture fires
     only on the transition from apart to touching, not while the fingers
     remain pinched together.

---

## 4. Coordinate Systems & Frame Mirroring

The webcam frame is **horizontally flipped** (`cv2.flip(frame, 1)`) before
being passed to MediaPipe.  This means:

- The display looks like a mirror (the user's right hand appears on the
  right side of the screen).
- MediaPipe's normalised x-coordinates are in the mirrored space.
- In this mirrored space, the user swiping their hand to the left
  corresponds to `dx < 0` in normalised coordinates.  This is used for
  the open-palm scroll gestures: left swipe = `SCROLL_FORWARD`, right
  swipe = `SCROLL_BACKWARD`.

MediaPipe's coordinate system:

| Axis | Direction | Range |
|---|---|---|
| x | Left to right (in the image) | 0.0 to 1.0 |
| y | Top to bottom | 0.0 to 1.0 |
| z | Depth (closer to camera = more negative) | Relative, unbounded |

Because y increases downward, a "swipe up" (hand moving toward the top of
the frame) produces a **negative** `dy`.

---

## 5. Cooldown & Deduplication

After a gesture fires, the `GestureDetector` records the current timestamp
for that gesture name.  On subsequent frames, if the same gesture would fire
again but fewer than `GESTURE_COOLDOWN_S` (0.6) seconds have elapsed, it is
suppressed.

Cooldowns are tracked **per gesture name**, not globally.  This means a
PITCH_UP can fire immediately after a TOGGLE_PLAYBACK, but two consecutive PITCH_UPs
must be at least 0.6 seconds apart.

If a gesture is on cooldown but a different detector matches, the loop
continues and the other gesture can still fire.

---

## 6. Confidence Scoring

Each detector produces a confidence value between 0.0 and 1.0:

- **Swipe gestures (pitch up/down):** `confidence = min(1.0, displacement / (threshold * 2))`.
  A swipe that exactly meets the minimum threshold gets 0.5; one that
  doubles the threshold gets 1.0.
- **Palm-swipe gestures (scroll forward/backward):** `confidence = min(1.0, displacement / (threshold * 2))`.
  Same scaling as index-finger swipes.
- **Pinch gesture (toggle playback):** Confidence is based on how close the
  thumb and index tips are relative to the threshold.  A pinch that just
  meets the threshold gets ~0.5; a tighter pinch approaches 1.0.

Confidence is informational -- it does not affect whether the gesture fires
(any match above the threshold fires).  It is included in the JSON output
so that downstream consumers can optionally filter or weight events.

---

## 7. Output Format

Each recognised gesture emits exactly one JSON line to **stdout**:

```json
{"gesture": "PITCH_UP", "confidence": 0.85, "timestamp": 1707900000.123}
```

| Field | Type | Description |
|---|---|---|
| `gesture` | string | One of: `PITCH_UP`, `PITCH_DOWN`, `TOGGLE_PLAYBACK`, `SCROLL_FORWARD`, `SCROLL_BACKWARD` |
| `confidence` | float | 0.0 to 1.0 (see Section 6) |
| `timestamp` | float | Unix epoch seconds when the gesture was recognised |

Informational messages (startup banner, errors) are written to **stderr**
so that stdout can be piped to a file or another process without
contamination.

---

## 8. Tuning Guide

All thresholds are in `src/config.py`.  Here is how to adjust them for
common scenarios:

**Gestures fire too easily (false positives):**

- Increase `SWIPE_MIN_DISPLACEMENT` (e.g. 0.12 -> 0.18).
- Increase `PALM_SWIPE_MIN_DISPLACEMENT` (e.g. 0.10 -> 0.15).
- Decrease `PINCH_DISTANCE_THRESHOLD` (e.g. 0.045 -> 0.035) to require a tighter pinch.
- Increase `PINCH_OPEN_THRESHOLD` (e.g. 0.07 -> 0.10) to require fingers to be farther apart before re-arming.
- Increase `GESTURE_COOLDOWN_S` (e.g. 0.6 -> 1.0).
- Increase `MIN_FRAMES_FOR_DETECTION` (e.g. 8 -> 12).

**Gestures are hard to trigger (false negatives):**

- Decrease the displacement / push thresholds.
- Decrease `SWIPE_DIRECTIONALITY_RATIO` or `PALM_SWIPE_DIRECTIONALITY_RATIO`
  (e.g. 1.8 -> 1.4) to allow slightly diagonal swipes.
- Increase `PINCH_DISTANCE_THRESHOLD` (e.g. 0.045 -> 0.06) to accept
  looser pinches.
- Decrease `PINCH_OPEN_THRESHOLD` (e.g. 0.07 -> 0.05) to re-arm more easily.
- Increase the frame windows (`SWIPE_FRAME_WINDOW`, `PALM_SWIPE_FRAME_WINDOW`,
  `PINCH_FRAME_WINDOW`) to analyse more history, which helps with slower
  gestures.

**Hand detection is unreliable:**

- Lower `MP_MIN_DETECTION_CONFIDENCE` (e.g. 0.7 -> 0.5).
- Lower `MP_MIN_TRACKING_CONFIDENCE` (e.g. 0.6 -> 0.4).
- Ensure good lighting and a non-cluttered background.

**Webcam resolution:**

- Change `CAMERA_WIDTH` and `CAMERA_HEIGHT`.  Higher resolution improves
  landmark accuracy but costs more CPU.  1280x720 is a good default.

---

## 9. Extending the System

**Adding a new gesture:**

1. Add a `GESTURE_MY_GESTURE` constant to `config.py` and append it to
   `ALL_GESTURES`.
2. Add any new thresholds to `config.py`.
3. Write a `_detect_my_gesture(self, buffer, finger_state)` method in
   `GestureDetector`.  It should return `(gesture_name, confidence)` or
   `None`.
4. Insert it into the `detectors` list in `GestureDetector.detect()` at the
   appropriate priority position (more specific gestures should come first).
5. No changes are needed in `main.py` or `overlay.py` -- they handle any
   gesture name generically.

**Switching to LIVE_STREAM mode:**

The current implementation uses MediaPipe's `VIDEO` running mode, which is
synchronous.  If you need asynchronous processing (e.g. to avoid blocking
the UI thread), you can switch to `LIVE_STREAM` mode by:

1. Changing `running_mode=RunningMode.LIVE_STREAM` in `HandTracker.__init__`.
2. Providing a `result_callback` in the options.
3. Calling `detect_async()` instead of `detect_for_video()`.

**Integrating with a music editor:**

The JSON-line output on stdout is designed for easy piping.  You can:

- Read it line-by-line from a subprocess in your music editor.
- Replace `_emit_json()` in `main.py` with a WebSocket send, HTTP POST,
  or direct function call.
- Import `GestureDetector` and `HandTracker` as a library and call them
  from your own event loop.
