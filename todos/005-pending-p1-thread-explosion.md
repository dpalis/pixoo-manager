---
id: "005"
title: "Thread explosion in network scanning"
status: pending
priority: p1
category: performance
source: performance-oracle-review
created: 2025-12-12
---

# Thread Explosion in Network Scanning

## Problem

The network discovery creates 100 threads simultaneously (one per IP in 192.168.1.1-100 range), which can cause:
- Thread pool exhaustion
- System resource starvation
- Application instability

## Location

- `app/services/pixoo_connection.py` - lines 114-161, `_scan_network()` method

## Recommended Fix

Use ThreadPoolExecutor with bounded concurrency:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def _scan_network(self, subnet: str = "192.168.1") -> str | None:
    """Scan network for Pixoo device with bounded concurrency."""

    def check_ip(ip: str) -> str | None:
        try:
            response = requests.get(
                f"http://{ip}:80/post",
                timeout=0.5,
                json={"Command": "Device/GetDeviceTime"}
            )
            if response.ok:
                return ip
        except:
            pass
        return None

    ips = [f"{subnet}.{i}" for i in range(1, 255)]

    # Limit to 20 concurrent connections
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(check_ip, ip): ip for ip in ips}
        for future in as_completed(futures, timeout=30):
            result = future.result()
            if result:
                return result

    return None
```

## Impact

- Severity: Critical (stability)
- Trigger: Any call to /api/discover
- Effect: Can crash or slow down the application
