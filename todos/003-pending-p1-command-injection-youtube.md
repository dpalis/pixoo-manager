---
id: "003"
title: "Command injection risk in YouTube downloader"
status: pending
priority: p1
category: security
source: security-sentinel-review
created: 2025-12-12
---

# Command Injection Risk in YouTube Downloader

## Problem

The YouTube downloader uses subprocess with user-provided URLs and time values. While yt-dlp is called as a module, the fallback FFmpeg command construction could be vulnerable.

## Location

- `app/services/youtube_downloader.py` - lines 175-193 (FFmpeg fallback)
- `app/services/youtube_downloader.py` - URL handling throughout

## Recommended Fix

1. **Validate YouTube URLs strictly**:
```python
import re

YOUTUBE_REGEX = re.compile(
    r'^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/)[\w-]{11}$'
)

def validate_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_REGEX.match(url))
```

2. **Use list arguments for subprocess** (never shell=True):
```python
# Good - arguments as list
subprocess.run(["ffmpeg", "-i", input_path, "-ss", str(start_time), ...])

# Bad - string with shell=True
subprocess.run(f"ffmpeg -i {input_path} -ss {start_time}", shell=True)
```

3. **Sanitize time values**:
```python
def sanitize_time(value: float) -> float:
    return max(0.0, min(float(value), 3600.0))  # Max 1 hour
```

## Impact

- Severity: Critical
- Attack Vector: User input (URL, time values)
- User Interaction: User must paste malicious URL
