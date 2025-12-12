---
id: "021"
title: "Potential memory leak from video frame extraction"
status: pending
priority: p3
category: performance
source: performance-oracle-review
created: 2025-12-12
---

# Potential Memory Leak from Video Frame Extraction

## Problem

Video frame extraction loads frames into memory without explicit cleanup. For long videos or many conversions, this could cause memory growth.

## Location

- `app/services/video_converter.py` - frame extraction functions

## Current Pattern

```python
def extract_frames(video_path: Path, ...) -> list[Image.Image]:
    frames = []
    clip = VideoFileClip(str(video_path))
    for t in frame_times:
        frame = clip.get_frame(t)
        img = Image.fromarray(frame)
        frames.append(img)
    clip.close()  # Video closed but frames still in memory
    return frames  # All frames held in memory
```

## Recommended Fix

Use generator pattern for large videos:

```python
def extract_frames_generator(video_path: Path, ...) -> Generator[Image.Image, None, None]:
    """Yield frames one at a time to reduce memory usage."""
    clip = VideoFileClip(str(video_path))
    try:
        for t in frame_times:
            frame = clip.get_frame(t)
            yield Image.fromarray(frame)
    finally:
        clip.close()
```

Or explicit cleanup:

```python
def extract_frames(video_path: Path, ...) -> list[Image.Image]:
    frames = []
    clip = VideoFileClip(str(video_path))
    try:
        for t in frame_times:
            frame = clip.get_frame(t)
            frames.append(Image.fromarray(frame))
    finally:
        clip.close()
        del clip  # Explicit deletion
        import gc
        gc.collect()  # Force garbage collection
    return frames
```

## Impact

- Severity: Nice-to-have
- Effect: Memory stability for long-running sessions
- Note: Current 10-second limit mitigates this issue
