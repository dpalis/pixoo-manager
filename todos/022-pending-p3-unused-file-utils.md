---
id: "022"
title: "Unused functions in file_utils.py"
status: pending
priority: p3
category: code-quality
source: code-simplicity-review
created: 2025-12-12
---

# Unused Functions in file_utils.py

## Problem

`file_utils.py` contains functions that are never called:
- `cleanup_file_async()` - async wrapper never used
- `cleanup_temp_dir()` - never called

## Location

- `app/services/file_utils.py`

## Verification

```bash
grep -r "cleanup_file_async\|cleanup_temp_dir" app/
# Only results are function definitions
```

## Current Code

```python
async def cleanup_file_async(path: Path) -> None:
    """Async wrapper for file cleanup."""
    cleanup_files(path)  # Never called anywhere

def cleanup_temp_dir(dir_path: Path) -> None:
    """Remove temp directory and contents."""
    if dir_path.exists():
        shutil.rmtree(dir_path)  # Never called
```

## Recommended Fix

Either:

1. **Remove unused functions**:
```python
# Delete the functions entirely
```

2. **Use them where appropriate**:
```python
# In routers that do async cleanup
await cleanup_file_async(temp_file)

# In shutdown lifecycle
cleanup_temp_dir(TEMP_DIR)
```

## Impact

- Severity: Nice-to-have
- Effect: Cleaner codebase
- Lines saved: ~15
