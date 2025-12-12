---
id: "018"
title: "Missing GET /api/config endpoint for agent access"
status: pending
priority: p3
category: agent-native
source: agent-native-review
created: 2025-12-12
---

# Missing GET /api/config Endpoint

## Problem

Application configuration (limits, supported formats) is only available in:
- HTML templates (Jinja2 variables)
- Python code (config.py)

No API endpoint exposes this to programmatic clients/agents.

## Location

- `app/config.py` - configuration values
- `app/main.py` - template context

## Current State

```python
# config.py
PIXOO_SIZE = 64
MAX_UPLOAD_FRAMES = 40
MAX_CONVERT_FRAMES = 92
MAX_VIDEO_DURATION = 10.0
MAX_FILE_SIZE = 500 * 1024 * 1024
```

Only accessible via:
```html
<!-- In templates -->
{{ max_file_size }}
```

## Recommended Fix

Add configuration endpoint:

```python
# In app/routers/connection.py or new app/routers/config.py

@router.get("/api/config")
async def get_config():
    """Return application configuration for programmatic clients."""
    return {
        "pixoo_size": PIXOO_SIZE,
        "max_upload_frames": MAX_UPLOAD_FRAMES,
        "max_convert_frames": MAX_CONVERT_FRAMES,
        "max_video_duration": MAX_VIDEO_DURATION,
        "max_file_size": MAX_FILE_SIZE,
        "supported_image_formats": ["gif", "png", "jpeg", "webp"],
        "supported_video_formats": ["mp4", "mov", "webm"],
    }
```

## Benefits

- Agents can discover limits before uploading
- CLI tools can validate input
- Integration tests can verify configuration

## Impact

- Severity: Nice-to-have
- Effect: Better agent/automation support
