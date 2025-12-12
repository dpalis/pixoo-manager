---
id: "010"
title: "Video boundary error in time selection"
status: pending
priority: p2
category: bug
source: data-integrity-guardian-review
created: 2025-12-12
---

# Video Boundary Error in Time Selection

## Problem

The video duration check uses strict inequality (`>`) instead of `>=`, allowing off-by-one frame errors at video boundaries.

## Location

- `app/services/video_converter.py` - line 117

## Current Code

```python
if time > duration:  # Should be >=
    time = duration
```

## Problem Scenario

- Video duration: 10.0 seconds
- User selects end time: 10.0 seconds
- Check passes (10.0 > 10.0 is False)
- FFmpeg tries to seek to frame at exactly 10.0, which may not exist

## Recommended Fix

```python
if time >= duration:
    time = duration - 0.001  # Or use last valid frame time
```

Or clamp to valid range:

```python
def clamp_time(time: float, duration: float) -> float:
    """Clamp time to valid video range."""
    return max(0.0, min(time, duration - 0.001))
```

## Impact

- Severity: Important
- Effect: Potential errors when selecting end of video
