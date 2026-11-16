import time

DAY_MS = 24 * 60 * 60 * 1000


def now_ms() -> int:
    return time.time_ns() // 1_000_000
