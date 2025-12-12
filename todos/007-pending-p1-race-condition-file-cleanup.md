---
id: "007"
title: "Race condition in file cleanup"
status: pending
priority: p1
category: data-integrity
source: data-integrity-guardian-review
created: 2025-12-12
---

# Race Condition in File Cleanup

## Problem

File cleanup operations can race with ongoing operations:
- Upload starts, file being processed
- Cleanup runs, deletes file mid-process
- Operation fails with confusing error

The `cleanup_files()` function in `file_utils.py` silently ignores all errors, masking potential issues.

## Location

- `app/services/file_utils.py` - `cleanup_files()` function (lines 203-215)
- Various routers that schedule cleanup after operations

## Current Code

```python
def cleanup_files(*paths: Path) -> None:
    """Remove arquivos temporarios."""
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass  # Silent failure!
```

## Recommended Fix

1. **Reference counting for files**:
```python
from threading import Lock

class FileTracker:
    def __init__(self):
        self._refs = {}
        self._lock = Lock()

    def acquire(self, path: Path) -> None:
        with self._lock:
            self._refs[path] = self._refs.get(path, 0) + 1

    def release(self, path: Path) -> bool:
        with self._lock:
            self._refs[path] = self._refs.get(path, 1) - 1
            if self._refs[path] <= 0:
                del self._refs[path]
                return True  # Safe to delete
            return False
```

2. **Log cleanup errors**:
```python
import logging
logger = logging.getLogger(__name__)

def cleanup_files(*paths: Path) -> None:
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            logger.warning(f"Failed to cleanup {path}: {e}")
```

## Impact

- Severity: Critical (data corruption possible)
- Effect: Random failures in upload/conversion operations
