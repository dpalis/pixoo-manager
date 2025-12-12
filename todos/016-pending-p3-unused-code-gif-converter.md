---
id: "016"
title: "280 lines of unused code in gif_converter.py"
status: pending
priority: p3
category: code-quality
source: code-simplicity-review
created: 2025-12-12
---

# Unused Code in gif_converter.py

## Problem

`gif_converter.py` (671 lines) contains ~280 lines of unused functions:
- `detect_edges()` - never called
- `majority_color_block_sampling()` - never called
- `darken_background()` - never called
- `focus_on_center()` - never called
- `create_preview()` - never called
- `image_to_single_frame_gif()` - never called

## Location

- `app/services/gif_converter.py`

## Verification

```bash
# Search for usages
grep -r "detect_edges\|majority_color_block_sampling\|darken_background\|focus_on_center\|create_preview\|image_to_single_frame_gif" app/
# Only results are the function definitions themselves
```

## Recommended Fix

Remove unused functions or:
1. Document them as "experimental/future use"
2. Move to a separate `gif_converter_experimental.py` module

```python
# If keeping for future use, mark clearly:
def detect_edges(img: Image.Image) -> Image.Image:
    """
    EXPERIMENTAL: Not currently used in production.
    Detects edges in image for artistic effects.
    """
    ...
```

## Impact

- Severity: Nice-to-have
- Effect: Reduced code complexity, easier maintenance
- Lines saved: ~280
