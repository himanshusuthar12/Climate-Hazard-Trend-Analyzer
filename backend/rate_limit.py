"""Simple in-memory rate limiter (per-IP, sliding window). No extra deps."""

import time
from collections import defaultdict, deque
import os

_hits: dict[str, deque] = defaultdict(deque)


def is_rate_limited(ip: str) -> bool:
    limit = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))
    now = time.time()
    window = _hits[ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        return True
    window.append(now)
    return False
