---
id: "002"
title: "Missing CSRF protection on state-changing endpoints"
status: pending
priority: p1
category: security
source: security-sentinel-review
created: 2025-12-12
---

# Missing CSRF Protection

## Problem

All POST endpoints lack CSRF token validation. A malicious website could trigger actions on behalf of a user who has the Pixoo Manager open.

## Location

- `app/routers/connection.py` - POST /api/connect, /api/disconnect
- `app/routers/gif_upload.py` - POST /api/gif/upload, /api/gif/send
- `app/routers/media_upload.py` - POST /api/media/upload, /api/media/convert
- `app/routers/youtube.py` - POST /api/youtube/download

## Recommended Fix

Since this is a local-only application, implement one of:

1. **SameSite cookies** (simplest for local app):
```python
# In main.py middleware
response.set_cookie("session", value, samesite="strict")
```

2. **Origin header validation**:
```python
@app.middleware("http")
async def validate_origin(request: Request, call_next):
    if request.method in ("POST", "PUT", "DELETE"):
        origin = request.headers.get("origin", "")
        if origin and "127.0.0.1" not in origin and "localhost" not in origin:
            return JSONResponse(status_code=403, content={"error": "Invalid origin"})
    return await call_next(request)
```

## Impact

- Severity: Critical
- Attack Vector: Network (cross-site)
- User Interaction: User must have app open while visiting malicious site
