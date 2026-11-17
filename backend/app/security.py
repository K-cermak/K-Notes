import json
import logging
import re
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' blob: data:",
        "font-src 'self'",
        "connect-src 'self'",
        "manifest-src 'self'",
        "worker-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
# FastAPI's API docs page loads Swagger UI from a CDN; it is a developer page outside the app itself.
DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
    "frame-ancestors 'none'"
)

_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    # Beyond SPEC 7: no other window keeps a handle on the app, and it never asks for these.
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=(), usb=()"),
]


class SecurityMiddleware:
    """Rejects cross-site state-changing API requests and adds security headers to every response.

    Written as plain ASGI middleware because Starlette's BaseHTTPMiddleware buffers streaming
    responses, which would break Server-Sent Events.
    """

    def __init__(self, app: ASGIApp, *, base_url: str, docs_path: str) -> None:
        self.app = app
        self.origin = base_url
        self.docs_path = docs_path

    def _cross_site(self, headers: dict[bytes, bytes]) -> bool:
        if b"authorization" in headers:
            return False
        origin = headers.get(b"origin")
        if origin is not None:
            return origin.decode("latin-1") != self.origin
        return headers.get(b"sec-fetch-site", b"same-origin") not in (b"same-origin", b"none")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        headers = dict(scope["headers"])
        if scope["method"] not in _SAFE_METHODS and path.startswith("/api/") and self._cross_site(headers):
            await _reject(send, headers.get(b"origin", b"another site").decode("latin-1"), self.origin)
            return
        csp = (DOCS_CSP if path == self.docs_path else CSP).encode()

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [
                    *message.get("headers", []),
                    *_HEADERS,
                    (b"content-security-policy", csp),
                ]
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def _reject(send: Send, came_from: str, expected: str) -> None:
    # Naming both addresses: the usual cause is APP_BASE_URL not matching the address in the browser.
    message = f"Cross-site request refused: it came from {came_from}, but APP_BASE_URL is {expected}"
    body = json.dumps({"code": "cross_origin", "message": message}).encode()
    headers: list[Any] = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
        *_HEADERS,
        (b"content-security-policy", CSP.encode()),
    ]
    await send({"type": "http.response.start", "status": 403, "headers": headers})
    await send({"type": "http.response.body", "body": body})


_TOKEN_PATH = re.compile(r"^/(invite|reset)/[^/?#]+")


class RedactTokensFilter(logging.Filter):
    """Keeps invite and reset tokens, which appear in page URLs, out of the access log."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], _TOKEN_PATH.sub(r"/\1/[redacted]", args[2]), *args[3:])
        return True


def install_log_redaction() -> None:
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, RedactTokensFilter) for f in access.filters):
        access.addFilter(RedactTokensFilter())
