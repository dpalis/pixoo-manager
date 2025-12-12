---
id: "014"
title: "Duplicate validation code across routers"
status: pending
priority: p2
category: code-quality
source: pattern-recognition-specialist-review
created: 2025-12-12
---

# Duplicate Validation Code Across Routers

## Problem

File validation logic is duplicated across multiple routers:
- Content type checking
- File size validation
- Extension validation

## Location

- `app/routers/gif_upload.py`
- `app/routers/media_upload.py`
- `app/routers/youtube.py`

## Example Duplication

```python
# In gif_upload.py
if file.content_type not in ALLOWED_TYPES:
    raise HTTPException(400, "Invalid file type")
if file.size > MAX_FILE_SIZE:
    raise HTTPException(413, "File too large")

# In media_upload.py - same pattern
if file.content_type not in MEDIA_TYPES:
    raise HTTPException(400, "Invalid file type")
if file.size > MAX_FILE_SIZE:
    raise HTTPException(413, "File too large")
```

## Recommended Fix

Create a shared validation module:

```python
# app/services/validators.py
from fastapi import HTTPException, UploadFile
from app.config import MAX_FILE_SIZE

def validate_file(
    file: UploadFile,
    allowed_types: set[str],
    max_size: int = MAX_FILE_SIZE
) -> None:
    """Validate uploaded file type and size."""
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    if file.size and file.size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum: {max_size // 1024 // 1024}MB"
        )
```

Usage in routers:

```python
from app.services.validators import validate_file

@router.post("/api/gif/upload")
async def upload_gif(file: UploadFile):
    validate_file(file, ALLOWED_GIF_TYPES)
    ...
```

## Impact

- Severity: Important
- Effect: Inconsistent validation, harder maintenance
