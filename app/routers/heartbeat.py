"""
Heartbeat endpoint for auto-shutdown functionality.

Browser sends periodic heartbeats. If no heartbeat is received
within the timeout period, the server shuts down automatically.
"""

import asyncio
import os
import sys
import time
from typing import Optional

from fastapi import APIRouter

router = APIRouter()

# Global state for heartbeat tracking
_last_heartbeat: float = time.time()
_shutdown_task: Optional[asyncio.Task] = None
_enabled: bool = True

# Configuration
HEARTBEAT_INTERVAL = 30  # Browser sends every 30s
INACTIVITY_TIMEOUT = 120  # Shutdown after 2 minutes without heartbeat


def disable_auto_shutdown():
    """Disable auto-shutdown (for development mode)."""
    global _enabled
    _enabled = False


def enable_auto_shutdown():
    """Enable auto-shutdown."""
    global _enabled
    _enabled = True


def is_auto_shutdown_enabled() -> bool:
    """Check if auto-shutdown is enabled."""
    return _enabled


def update_heartbeat():
    """Update the last heartbeat timestamp."""
    global _last_heartbeat
    _last_heartbeat = time.time()


def get_time_since_heartbeat() -> float:
    """Get seconds since last heartbeat."""
    return time.time() - _last_heartbeat


@router.post("/api/heartbeat")
async def heartbeat():
    """
    Receive heartbeat from browser.

    Called periodically by the frontend to indicate the browser is still open.
    """
    update_heartbeat()
    return {"status": "ok", "timestamp": _last_heartbeat}


@router.get("/api/heartbeat/status")
async def heartbeat_status():
    """
    Get heartbeat status.

    Useful for debugging.
    """
    return {
        "enabled": _enabled,
        "last_heartbeat": _last_heartbeat,
        "seconds_since": get_time_since_heartbeat(),
        "timeout": INACTIVITY_TIMEOUT
    }


async def check_inactivity():
    """
    Background task that checks for inactivity.

    Shuts down the application if no heartbeat is received within timeout.
    """
    global _shutdown_task

    while True:
        await asyncio.sleep(30)  # Check every 30 seconds

        if not _enabled:
            continue

        time_since = get_time_since_heartbeat()

        if time_since > INACTIVITY_TIMEOUT:
            print(f"No heartbeat for {time_since:.0f}s. Shutting down...")
            # Try to quit rumps gracefully
            try:
                import rumps
                rumps.quit_application()
            except (ImportError, AttributeError):
                pass
            # Exit the process
            os._exit(0)


def start_inactivity_monitor():
    """
    Start the inactivity monitor task.

    Should be called from FastAPI startup event.
    """
    global _shutdown_task

    # Don't start if disabled
    if not _enabled:
        return None

    # Update heartbeat to start fresh
    update_heartbeat()

    # Create the task
    _shutdown_task = asyncio.create_task(check_inactivity())
    return _shutdown_task


def stop_inactivity_monitor():
    """
    Stop the inactivity monitor task.

    Should be called from FastAPI shutdown event.
    """
    global _shutdown_task
    if _shutdown_task:
        _shutdown_task.cancel()
        _shutdown_task = None
