---
id: "011"
title: "YouTube fallback downloads entire video instead of segment"
status: pending
priority: p2
category: bug
source: data-integrity-guardian-review
created: 2025-12-12
---

# YouTube Fallback Downloads Entire Video

## Problem

When the primary download method fails, the fallback downloads the entire video instead of just the selected segment. This wastes bandwidth and time.

## Location

- `app/services/youtube_downloader.py` - lines 175-193

## Current Code

```python
# Fallback: download entire video
ydl_opts = {
    'format': 'best[height<=480]',
    'outtmpl': str(output_path),
}
# start_time and end_time are ignored!
```

## Recommended Fix

```python
# Fallback: download with FFmpeg post-processing
ydl_opts = {
    'format': 'best[height<=480]',
    'outtmpl': str(temp_full_path),
    'postprocessors': [{
        'key': 'FFmpegVideoConvertor',
        'preferedformat': 'mp4',
    }],
    'postprocessor_args': [
        '-ss', str(start_time),
        '-t', str(end_time - start_time),
    ],
}
```

Or download full video then trim:

```python
# After download
if start_time > 0 or end_time < duration:
    trim_video(temp_full_path, output_path, start_time, end_time)
```

## Impact

- Severity: Important
- Effect: Downloads 10x more data than needed for long videos
- User Experience: Slow downloads, wasted bandwidth
