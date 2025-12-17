"""
Heartbeat endpoint for auto-shutdown functionality.

Browser sends periodic heartbeats. If no heartbeat is received
within the timeout period, the server shuts down automatically.
"""

import asyncio
import os
import signal
import time
from typing import Optional

from fastapi import APIRouter, Request

from app.middleware import RateLimiter, check_rate_limit

router = APIRouter()

# Thread-safe state using asyncio.Lock
_lock = asyncio.Lock()
_last_heartbeat: float = time.time()
_shutdown_task: Optional[asyncio.Task] = None
_enabled: bool = True

# Rate limiter: max 20 requests per minute (generous for multiple tabs/reconnections)
_heartbeat_limiter = RateLimiter(max_requests=20, window_seconds=60)

# Configuration
HEARTBEAT_INTERVAL = 20  # Browser sends every 20s
INACTIVITY_TIMEOUT = 120  # Shutdown after 2 minutes without heartbeat


async def _get_enabled() -> bool:
    """Thread-safe getter for _enabled."""
    async with _lock:
        return _enabled


async def _set_enabled(value: bool) -> None:
    """Thread-safe setter for _enabled."""
    global _enabled
    async with _lock:
        _enabled = value


async def _get_last_heartbeat() -> float:
    """Thread-safe getter for _last_heartbeat."""
    async with _lock:
        return _last_heartbeat


async def _update_heartbeat() -> float:
    """Thread-safe update of _last_heartbeat. Returns new timestamp."""
    global _last_heartbeat
    async with _lock:
        _last_heartbeat = time.time()
        return _last_heartbeat


def disable_auto_shutdown():
    """
    Disable auto-shutdown (for development mode).

    Note: This is sync for use during startup before event loop.
    """
    global _enabled
    _enabled = False


def start_inactivity_monitor():
    """
    Start the inactivity monitor task.

    Should be called from FastAPI startup event.
    """
    global _shutdown_task, _last_heartbeat

    # Don't start if disabled
    if not _enabled:
        return None

    # Update heartbeat to start fresh
    _last_heartbeat = time.time()

    # Create the task
    _shutdown_task = asyncio.create_task(_check_inactivity())
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


@router.post("/api/heartbeat")
async def heartbeat(request: Request):
    """
    Receive heartbeat from browser.

    Called periodically by the frontend to indicate the browser is still open.
    Rate limited to prevent abuse.
    """
    # Rate limit check (uses IP as key for defense in depth)
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(_heartbeat_limiter, client_ip)

    timestamp = await _update_heartbeat()
    print(f"♥ Heartbeat received @ {timestamp:.0f}")
    return {"status": "ok", "timestamp": timestamp}


@router.get("/api/heartbeat/status")
async def heartbeat_status():
    """
    Get heartbeat status.

    Returns only non-sensitive operational data.
    """
    enabled = await _get_enabled()
    return {
        "enabled": enabled,
        "timeout": INACTIVITY_TIMEOUT
    }


@router.post("/api/system/shutdown")
async def shutdown():
    """
    Trigger graceful shutdown via API.

    Agent-native endpoint for menu bar "Quit" action.
    """
    asyncio.create_task(_graceful_shutdown())
    return {"status": "shutting_down"}


async def _check_inactivity():
    """
    Background task that checks for inactivity.

    Shuts down the application if no heartbeat is received within timeout.
    """
    print(f"[Monitor] Inactivity monitor started (timeout: {INACTIVITY_TIMEOUT}s)")
    while True:
        await asyncio.sleep(30)  # Check every 30 seconds

        enabled = await _get_enabled()
        if not enabled:
            continue

        last = await _get_last_heartbeat()
        time_since = time.time() - last
        print(f"[Monitor] Last heartbeat: {time_since:.0f}s ago")

        if time_since > INACTIVITY_TIMEOUT:
            print(f"⚠️ No heartbeat for {time_since:.0f}s. Shutting down...")
            await _graceful_shutdown()
            return


async def _graceful_shutdown():
    """
    Perform graceful shutdown using SIGTERM.

    This allows FastAPI's lifespan to run cleanup (disconnect Pixoo,
    clean temp files, etc.) instead of os._exit() which bypasses everything.
    """
    # Give time for response to be sent
    await asyncio.sleep(0.5)

    # Try to quit rumps gracefully (macOS menu bar)
    try:
        import rumps
        rumps.quit_application()
    except (ImportError, AttributeError):
        pass

    # Send SIGTERM to self for graceful shutdown
    os.kill(os.getpid(), signal.SIGTERM)
