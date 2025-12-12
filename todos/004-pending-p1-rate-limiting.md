---
id: "004"
title: "No rate limiting on expensive operations"
status: pending
priority: p1
category: security
source: security-sentinel-review
created: 2025-12-12
---

# No Rate Limiting on Expensive Operations

## Problem

Expensive operations like video conversion, YouTube download, and network scanning have no rate limiting. An attacker or misconfigured client could exhaust server resources.

## Location

- `app/routers/youtube.py` - /api/youtube/download (downloads video)
- `app/routers/media_upload.py` - /api/media/convert (CPU intensive)
- `app/routers/connection.py` - /api/discover (100 threads for network scan)

## Recommended Fix

Implement simple in-memory rate limiting:

```python
from collections import defaultdict
from time import time

class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests = defaultdict(list)

    def is_allowed(self, key: str = "global") -> bool:
        now = time()
        # Remove old requests
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window]
        if len(self.requests[key]) >= self.max_requests:
            return False
        self.requests[key].append(now)
        return True

# Usage in router
youtube_limiter = RateLimiter(max_requests=5, window_seconds=60)

@router.post("/api/youtube/download")
async def download(request: DownloadRequest):
    if not youtube_limiter.is_allowed():
        raise HTTPException(429, "Too many requests")
    ...
```

## Impact

- Severity: Critical (DoS potential)
- Attack Vector: Network
- User Interaction: None required
