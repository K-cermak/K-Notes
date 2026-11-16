import asyncio
import threading
from dataclasses import dataclass, field


@dataclass(eq=False)
class Listener:
    """One open event stream. Only the newest counter value matters, so notifications coalesce."""

    user_id: str
    loop: asyncio.AbstractEventLoop
    seq: int = 0
    wake: asyncio.Event = field(default_factory=asyncio.Event)

    def notify(self, seq: int) -> None:
        self.seq = max(self.seq, seq)
        self.wake.set()


class EventHub:
    """In-process registry of event streams per user (SPEC 2: one server process, no broker).

    publish() is called from the thread pool that runs the sync endpoints, so it hands the
    notification to each stream's event loop with call_soon_threadsafe.
    """

    def __init__(self) -> None:
        self._listeners: dict[str, set[Listener]] = {}
        self._lock = threading.Lock()
        self.closed = False

    def subscribe(self, user_id: str) -> Listener:
        listener = Listener(user_id=user_id, loop=asyncio.get_running_loop())
        with self._lock:
            self._listeners.setdefault(user_id, set()).add(listener)
        return listener

    def unsubscribe(self, listener: Listener) -> None:
        with self._lock:
            listeners = self._listeners.get(listener.user_id)
            if listeners is not None:
                listeners.discard(listener)
                if not listeners:
                    del self._listeners[listener.user_id]

    def publish(self, user_id: str, seq: int) -> None:
        with self._lock:
            listeners = list(self._listeners.get(user_id, ()))
        for listener in listeners:
            listener.loop.call_soon_threadsafe(listener.notify, seq)

    def count(self, user_id: str) -> int:
        with self._lock:
            return len(self._listeners.get(user_id, ()))

    def close(self) -> None:
        """Ends every stream, so shutdown does not wait for clients that never disconnect."""
        self.closed = True
        with self._lock:
            listeners = [each for group in self._listeners.values() for each in group]
        for listener in listeners:
            listener.loop.call_soon_threadsafe(listener.wake.set)
