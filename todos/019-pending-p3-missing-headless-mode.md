---
id: "019"
title: "Missing headless mode for server-only operation"
status: pending
priority: p3
category: agent-native
source: agent-native-review
created: 2025-12-12
---

# Missing Headless Mode

## Problem

The application always opens browser on startup, making it unsuitable for:
- Server-only deployment
- Headless environments
- CI/CD pipelines
- Agent/automation use

## Location

- `app/main.py` - `lifespan()` function

## Current Code

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    webbrowser.open(f"http://{HOST}:{PORT}")  # Always opens!
    yield
```

## Recommended Fix

Add environment variable for headless mode:

```python
import os

HEADLESS = os.getenv("PIXOO_HEADLESS", "false").lower() == "true"

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not HEADLESS:
        webbrowser.open(f"http://{HOST}:{PORT}")
    yield
```

Or command-line argument:

```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--headless", action="store_true", help="Run without opening browser")
args = parser.parse_args()

# In lifespan
if not args.headless:
    webbrowser.open(...)
```

## Usage

```bash
# Normal mode (opens browser)
python -m app.main

# Headless mode (API only)
PIXOO_HEADLESS=true python -m app.main
# or
python -m app.main --headless
```

## Impact

- Severity: Nice-to-have
- Effect: Enables automation and server deployment
