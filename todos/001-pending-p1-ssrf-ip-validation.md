---
id: "001"
title: "SSRF vulnerability via missing IP validation"
status: pending
priority: p1
category: security
source: security-sentinel-review
created: 2025-12-12
---

# SSRF Vulnerability via Missing IP Validation

## Problem

The `/api/connect` endpoint accepts any IP address without validation, allowing Server-Side Request Forgery attacks. An attacker could make the server connect to internal services, cloud metadata endpoints (169.254.169.254), or other malicious targets.

## Location

- `app/routers/connection.py` - `/api/connect` endpoint
- `app/services/pixoo_connection.py` - `connect()` method

## Recommended Fix

Add IP address validation to reject:
- Private network ranges (10.x.x.x, 172.16-31.x.x, 192.168.x.x) if not expected
- Loopback addresses (127.x.x.x)
- Link-local addresses (169.254.x.x)
- Cloud metadata endpoints

```python
import ipaddress

def is_safe_ip(ip_str: str) -> bool:
    """Validate IP is a safe local network address."""
    try:
        ip = ipaddress.ip_address(ip_str)
        # Allow only private network IPs (typical for Pixoo)
        if ip.is_private and not ip.is_loopback and not ip.is_link_local:
            return True
        return False
    except ValueError:
        return False
```

## Impact

- Severity: Critical
- Attack Vector: Network
- User Interaction: None required
