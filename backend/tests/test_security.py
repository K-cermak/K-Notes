import logging
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.security import RedactTokensFilter
from app.services import throttle as throttle_module
from app.services.throttle import LoginThrottle
from tests.conftest import ADMIN

LOGIN = {"email": ADMIN["email"], "password": ADMIN["password"]}


def test_cross_origin_writes_are_refused(admin: TestClient, new_client: Callable[[], TestClient]) -> None:
    response = admin.patch(
        "/api/v1/me", json={"display_name": "Evil"}, headers={"origin": "https://evil.test"}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "cross_origin"
    login = new_client().post("/api/v1/auth/login", json=LOGIN, headers={"origin": "https://evil.test"})
    assert login.status_code == 403
    assert admin.get("/api/v1/me").json()["display_name"] == "Admin"


def test_same_origin_writes_are_allowed(admin: TestClient) -> None:
    response = admin.patch("/api/v1/me", json={"display_name": "Ok"}, headers={"origin": "http://testserver"})
    assert response.status_code == 200


def test_sec_fetch_site_is_checked_without_origin(admin: TestClient) -> None:
    for site, expected in (("cross-site", 403), ("same-site", 403), ("same-origin", 200), ("none", 200)):
        response = admin.patch("/api/v1/me", json={}, headers={"sec-fetch-site": site})
        assert response.status_code == expected, site


def test_cross_origin_reads_are_not_blocked(admin: TestClient) -> None:
    assert admin.get("/api/v1/config", headers={"origin": "https://evil.test"}).status_code == 200


def test_security_headers(client: TestClient) -> None:
    for path in ("/", "/api/v1/config", "/api/v1/nope"):
        headers = client.get(path).headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"
        assert headers["cross-origin-opener-policy"] == "same-origin"
        assert "camera=()" in headers["permissions-policy"]
        csp = headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "unsafe-inline" not in csp


def test_api_docs_page_loads(client: TestClient) -> None:
    response = client.get("/api/v1/docs")
    assert response.status_code == 200
    assert "cdn.jsdelivr.net" in response.headers["content-security-policy"]


def test_throttle_delays_grow_and_expire(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(throttle_module.time, "monotonic", lambda: now[0])
    throttle = LoginThrottle(free_per_account=2, free_per_ip=100)
    for _ in range(2):
        assert throttle.retry_after("a", "ip") == 0
        throttle.failed("a", "ip")
    assert throttle.retry_after("a", "ip") == 1
    throttle.failed("a", "ip")
    assert throttle.retry_after("a", "ip") == 2
    assert throttle.retry_after("b", "ip") == 0
    now[0] += 3
    assert throttle.retry_after("a", "ip") == 0
    now[0] += 2 * 60 * 60
    throttle.failed("a", "ip")
    assert throttle.retry_after("a", "ip") == 0


def test_throttle_counts_per_ip_across_accounts() -> None:
    throttle = LoginThrottle(free_per_account=100, free_per_ip=3)
    for account in ("a", "b", "c"):
        throttle.failed(account, "1.2.3.4")
    assert throttle.retry_after("d", "1.2.3.4") > 0
    assert throttle.retry_after("d", "5.6.7.8") == 0


def test_success_resets_the_account_counter() -> None:
    throttle = LoginThrottle(free_per_account=1, free_per_ip=100)
    throttle.failed("a", "ip")
    throttle.succeeded("a")
    assert throttle.retry_after("a", "ip") == 0


def test_access_log_redacts_link_tokens() -> None:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("1.2.3.4", "GET", "/invite/s3cret?x=1", "1.1", 200),
        None,
    )
    RedactTokensFilter().filter(record)
    assert "s3cret" not in record.getMessage()
    assert "/invite/[redacted]?x=1" in record.getMessage()
