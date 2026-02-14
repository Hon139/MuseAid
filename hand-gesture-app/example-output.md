# Example JSON Output

The app emits **one JSON object per line** (JSONL format) to stdout whenever a gesture is detected.

## Single Gesture Event

```json
{"gesture": "PITCH_UP", "confidence": 0.85, "timestamp": 1707900000.123}
```

## Full Session Example (Multiple Lines)

```json
{"gesture": "TOGGLE_PLAYBACK", "confidence": 0.923, "timestamp": 1707900001.456}
{"gesture": "PITCH_UP", "confidence": 0.871, "timestamp": 1707900003.789}
{"gesture": "SCROLL_FORWARD", "confidence": 0.654, "timestamp": 1707900006.012}
{"gesture": "PITCH_DOWN", "confidence": 0.912, "timestamp": 1707900008.345}
{"gesture": "SCROLL_BACKWARD", "confidence": 0.788, "timestamp": 1707900010.678}
{"gesture": "TOGGLE_PLAYBACK", "confidence": 0.845, "timestamp": 1707900013.901}
```

## Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `gesture` | `string` | One of: `PITCH_UP`, `PITCH_DOWN`, `TOGGLE_PLAYBACK`, `SCROLL_FORWARD`, `SCROLL_BACKWARD` |
| `confidence` | `float` | Detection confidence in [0, 1], rounded to 3 decimal places |
| `timestamp` | `float` | Unix epoch timestamp when the gesture was detected, rounded to 3 decimal places |

## Capturing Output

Each line is a self-contained JSON object, flushed immediately to stdout. Informational/error logs go to stderr, so you can cleanly capture just the gesture data with:

```bash
uv run python -m src.main > gestures.jsonl
```
