import logging
import sys

import uvicorn

from app.config import ConfigError, load_settings
from app.main import create_app


def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        sys.exit(2)
    logging.basicConfig(level=settings.log_level.upper(), format="%(levelname)-9s %(name)s: %(message)s")
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
    )


if __name__ == "__main__":
    main()
