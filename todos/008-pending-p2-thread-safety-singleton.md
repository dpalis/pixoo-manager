---
id: "008"
title: "Thread safety issues in PixooConnection singleton"
status: pending
priority: p2
category: architecture
source: architecture-strategist-review
created: 2025-12-12
---

# Thread Safety Issues in PixooConnection Singleton

## Problem

The `PixooConnection` singleton has multiple thread-safety issues:
1. Properties `connected` and `ip` are not protected
2. Multiple threads could race during initialization
3. State changes are not atomic

## Location

- `app/services/pixoo_connection.py` - entire class

## Current Issues

```python
class PixooConnection:
    _instance = None
    _ip: str | None = None
    _connected: bool = False

    def __new__(cls):
        if cls._instance is None:  # Race condition here!
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def connected(self) -> bool:
        return self._connected  # Not thread-safe read
```

## Recommended Fix

```python
import threading

class PixooConnection:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # Double-check locking
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._state_lock = threading.RLock()
            self._ip: str | None = None
            self._connected: bool = False
            self._initialized = True

    @property
    def connected(self) -> bool:
        with self._state_lock:
            return self._connected

    def connect(self, ip: str) -> bool:
        with self._state_lock:
            # ... connection logic
            self._ip = ip
            self._connected = True
```

## Impact

- Severity: Important
- Effect: Potential race conditions with concurrent requests
