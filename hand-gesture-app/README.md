# Hand Gesture Recognition

Real-time hand gesture recognition using OpenCV and MediaPipe.  Detects five
gestures from a live webcam feed, displays visual feedback in an overlay
window, and emits structured JSON to stdout for downstream consumption (e.g.
a music editor).

## Prerequisites

- Python 3.10+
- A webcam
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

```bash
# Clone / navigate to the project directory
cd hand-gesture-app

# Install dependencies
uv sync
```

## Running

```bash
uv run python -m src.main
```

Press **q** in the OpenCV window to quit.

### Capturing JSON output

Gesture events are printed as JSON lines to **stdout**.  Informational
messages go to stderr, so you can pipe cleanly:

```bash
uv run python -m src.main > gestures.jsonl
```

Each line looks like:

```json
{"gesture": "PITCH_UP", "confidence": 0.85, "timestamp": 1707900000.123}
```

## Supported Gestures

| Gesture | How to perform | JSON name |
|---|---|---|
| **Pitch Up** | Extend only your index finger and swipe upward | `PITCH_UP` |
| **Pitch Down** | Extend only your index finger and swipe downward | `PITCH_DOWN` |
| **Toggle Playback** | Tap your thumb and index finger together (pinch) | `TOGGLE_PLAYBACK` |
| **Scroll Forward** | Open your palm flat (4+ fingers extended) and swipe left | `SCROLL_FORWARD` |
| **Scroll Backward** | Open your palm flat (4+ fingers extended) and swipe right | `SCROLL_BACKWARD` |

## Visual Overlay

The webcam window shows:

- **Hand landmarks** and bone connections drawn on your hand.
- **Gesture label** (large green text, top-left) showing the most recently
  detected gesture for ~1 second.
- **Finger state** (bottom bar) showing which fingers are UP or down.
- **Motion trails** for the index fingertip (orange) and, when the palm is
  open, for the palm centre (green).

## Tuning

All detection thresholds are in `src/config.py`.  Key parameters:

| Parameter | Default | Description |
|---|---|---|
| `SWIPE_MIN_DISPLACEMENT` | `0.12` | Minimum normalised distance for an index-finger swipe to register |
| `SWIPE_DIRECTIONALITY_RATIO` | `1.8` | How much more the primary axis must move vs the off-axis |
| `PALM_SWIPE_MIN_DISPLACEMENT` | `0.10` | Minimum normalised distance for an open-palm swipe to register |
| `PALM_SWIPE_DIRECTIONALITY_RATIO` | `1.8` | Directionality ratio for palm swipes |
| `PINCH_DISTANCE_THRESHOLD` | `0.045` | Maximum thumb-index distance to count as a pinch |
| `GESTURE_COOLDOWN_S` | `0.6` | Seconds to ignore repeated detections of the same gesture |
| `BUFFER_SIZE` | `20` | Number of frames kept in the motion history buffer |
| `MP_MIN_DETECTION_CONFIDENCE` | `0.7` | MediaPipe hand detection confidence |
| `MP_MIN_TRACKING_CONFIDENCE` | `0.6` | MediaPipe hand tracking confidence |

If gestures fire too easily, increase the displacement thresholds or the
cooldown.  If they are hard to trigger, lower them.

## Project Structure

```
hand-gesture-app/
  pyproject.toml          # uv project config & dependencies
  README.md               # this file
  src/
    __init__.py
    main.py               # entry point: webcam loop, orchestration
    hand_tracker.py        # MediaPipe Hands wrapper
    gesture_detector.py    # gesture classification logic
    motion_buffer.py       # circular buffer for landmark history
    finger_state.py        # which fingers are extended
    overlay.py             # drawing landmarks, labels, trails
    config.py              # all tunable constants
```
