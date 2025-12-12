---
id: "012"
title: "In-memory upload state has no TTL cleanup"
status: pending
priority: p2
category: data-integrity
source: data-integrity-guardian-review
created: 2025-12-12
---

# In-Memory Upload State Has No TTL Cleanup

## Problem

Upload tracking dictionaries (`_uploads`) in routers grow indefinitely:
- No TTL (time-to-live) for entries
- No periodic cleanup
- Memory leak over long-running sessions

## Location

- `app/routers/gif_upload.py` - `_uploads` dict
- `app/routers/media_upload.py` - `_uploads` dict
- `app/routers/youtube.py` - `_downloads` dict

## Current Code

```python
_uploads: dict[str, UploadInfo] = {}  # Grows forever!

@router.post("/api/gif/upload")
async def upload_gif(...):
    upload_id = str(uuid.uuid4())
    _uploads[upload_id] = UploadInfo(...)
    # Never cleaned up if user abandons upload
```

## Recommended Fix

```python
from dataclasses import dataclass, field
from time import time

@dataclass
class UploadInfo:
    path: Path
    metadata: GifMetadata
    created_at: float = field(default_factory=time)

_uploads: dict[str, UploadInfo] = {}
UPLOAD_TTL = 3600  # 1 hour

def cleanup_stale_uploads() -> None:
    """Remove uploads older than TTL."""
    now = time()
    stale_ids = [
        uid for uid, info in _uploads.items()
        if now - info.created_at > UPLOAD_TTL
    ]
    for uid in stale_ids:
        info = _uploads.pop(uid)
        cleanup_files(info.path)

# Call periodically or on each request
```

Or use a TTL cache library:

```python
from cachetools import TTLCache

_uploads = TTLCache(maxsize=100, ttl=3600)
```

## Impact

- Severity: Important
- Effect: Memory growth over time, orphaned temp files
