---
id: "006"
title: "No application shutdown cleanup"
status: pending
priority: p1
category: data-integrity
source: data-integrity-guardian-review
created: 2025-12-12
---

# No Application Shutdown Cleanup

## Problem

The application lifespan only handles startup (opening browser) but has no shutdown cleanup:
- Temporary files remain on disk
- In-memory upload tracking is lost
- No graceful disconnect from Pixoo device
- Potential resource leaks

## Location

- `app/main.py` - `lifespan()` function (lines 23-27)

## Current Code

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Abre o navegador quando o servidor inicia."""
    webbrowser.open(f"http://{HOST}:{PORT}")
    yield
    # No cleanup!
```

## Recommended Fix

```python
import tempfile
import shutil
from app.services.pixoo_connection import pixoo_connection
from app.services.file_utils import TEMP_DIR

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle with proper cleanup."""
    # Startup
    webbrowser.open(f"http://{HOST}:{PORT}")

    yield

    # Shutdown cleanup
    try:
        # Disconnect from Pixoo
        if pixoo_connection.connected:
            pixoo_connection.disconnect()

        # Clean temp directory
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR, ignore_errors=True)

        print("Cleanup completed successfully")
    except Exception as e:
        print(f"Cleanup error: {e}")
```

## Impact

- Severity: Critical (resource leak)
- Effect: Temp files accumulate over time, memory leaks
