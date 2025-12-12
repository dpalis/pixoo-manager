---
id: "009"
title: "Integer division bug in frame duration calculation"
status: pending
priority: p2
category: bug
source: data-integrity-guardian-review
created: 2025-12-12
---

# Integer Division Bug in Frame Duration Calculation

## Problem

Frame duration calculation uses integer division (`//`) which truncates fractional milliseconds, causing timing drift in animations.

## Location

- `app/services/pixoo_upload.py` - line 129

## Current Code

```python
avg_duration = sum(durations) // len(durations)  # Integer division!
```

## Example

If durations are `[100, 100, 100, 50]`:
- Sum = 350
- Count = 4
- Integer division: 350 // 4 = 87
- Float division: 350 / 4 = 87.5

Over many frames, this causes noticeable timing drift.

## Recommended Fix

```python
avg_duration = round(sum(durations) / len(durations))
```

Or preserve precision until the final use:

```python
avg_duration = sum(durations) / len(durations)
# Round only when sending to Pixoo API
pixoo_duration = int(round(avg_duration))
```

## Impact

- Severity: Important
- Effect: GIF animations may play slightly faster/slower than intended
