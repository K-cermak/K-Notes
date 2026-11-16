import threading
import time
from dataclasses import dataclass

_FORGET_AFTER_S = 60 * 60
_MAX_DELAY_S = 15 * 60


@dataclass
class _Failures:
    count: int
    last: float


class LoginThrottle:
    """Growing delays after failed logins, counted per account and per client address.

    In memory only: the app runs as one process, and a restart forgetting the counters is harmless.
    """

    def __init__(self, free_per_account: int = 5, free_per_ip: int = 20) -> None:
        self._free = {"account": free_per_account, "ip": free_per_ip}
        self._failures: dict[tuple[str, str], _Failures] = {}
        self._lock = threading.Lock()

    def _delay(self, kind: str, count: int) -> float:
        over = count - self._free[kind]
        return 0 if over < 0 else min(2.0**over, _MAX_DELAY_S)

    def retry_after(self, account: str, ip: str) -> int:
        """Seconds the caller must wait before another attempt, or 0."""
        now = time.monotonic()
        wait = 0.0
        with self._lock:
            for key in (("account", account), ("ip", ip)):
                failures = self._failures.get(key)
                if failures is None:
                    continue
                if now - failures.last > _FORGET_AFTER_S:
                    del self._failures[key]
                    continue
                wait = max(wait, failures.last + self._delay(key[0], failures.count) - now)
        return int(wait + 0.999) if wait > 0 else 0

    def failed(self, account: str, ip: str) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._failures) > 10_000:
                self._prune(now)
            for key in (("account", account), ("ip", ip)):
                failures = self._failures.get(key)
                if failures is None or now - failures.last > _FORGET_AFTER_S:
                    failures = self._failures[key] = _Failures(0, now)
                failures.count += 1
                failures.last = now

    def succeeded(self, account: str) -> None:
        with self._lock:
            self._failures.pop(("account", account), None)

    def _prune(self, now: float) -> None:
        stale = [key for key, f in self._failures.items() if now - f.last > _FORGET_AFTER_S]
        for key in stale:
            del self._failures[key]
