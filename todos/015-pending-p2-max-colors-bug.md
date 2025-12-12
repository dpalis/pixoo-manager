---
id: "015"
title: "Bug: options.max_colors attribute doesn't exist"
status: pending
priority: p2
category: bug
source: code-simplicity-review
created: 2025-12-12
---

# Bug: options.max_colors Attribute Doesn't Exist

## Problem

`video_converter.py` references `options.max_colors` but `ConvertOptions` dataclass doesn't have this attribute.

## Location

- `app/services/video_converter.py` - line 196

## Current Code

```python
# In video_converter.py
if options.max_colors:  # AttributeError!
    img = quantize_colors(img, options.max_colors)
```

But in `gif_converter.py`:

```python
@dataclass
class ConvertOptions:
    led_optimize: bool = True
    target_size: int = 64
    enhance: bool = True
    num_colors: int = 64  # It's num_colors, not max_colors!
```

## Recommended Fix

Change reference to correct attribute name:

```python
# In video_converter.py
if options.num_colors:
    img = quantize_colors(img, options.num_colors)
```

Or add the missing attribute to ConvertOptions if different behavior is intended.

## Impact

- Severity: Important
- Effect: AttributeError crash when converting videos
- Easy Fix: Single line change
