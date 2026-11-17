import logging
import sys
from urllib.parse import urlsplit

import uvicorn

from app.config import ConfigError, load_settings
from app.main import create_app

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        sys.exit(2)
    logging.basicConfig(level=settings.log_level.upper(), format="%(levelname)-9s %(name)s: %(message)s")
    if not settings.secure_cookies and urlsplit(settings.base_url).hostname not in LOCAL_HOSTS:
        # Not fatal, as a first try on a LAN should work, but offline use and installing need HTTPS.
        logging.getLogger("app").warning(
            "APP_BASE_URL %s is not https: browsers allow the offline app and installing it only "
            "over HTTPS (or on localhost), and session cookies are sent without the Secure flag. "
            "Put a reverse proxy with HTTPS in front of the app.",
            settings.base_url,
        )
    # One worker only: SSE fan-out lives in process memory and SQLite has a single writer.
    uvicorn.run(
        create_app(settings),
        host="0.0.0.0",  # noqa: S104
        port=8000,
        workers=1,
        log_level=settings.log_level,
        proxy_headers=bool(settings.trusted_proxies),
        forwarded_allow_ips=settings.trusted_proxies or None,
        server_header=False,
        # Open event streams would otherwise hold up a restart until every client disconnects.
        timeout_graceful_shutdown=5,
    )


if __name__ == "__main__":
    main()
