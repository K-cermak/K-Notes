from fastapi.testclient import TestClient


def test_client_routes_fall_back_to_index(client: TestClient) -> None:
    for path in ("/", "/note/123", "/settings/profile"):
        response = client.get(path)
        assert response.status_code == 200
        assert "<title>index</title>" in response.text
        assert response.headers["cache-control"] == "no-cache"


def test_fingerprinted_assets_are_immutable(client: TestClient) -> None:
    response = client.get("/assets/app-abc123.js")
    assert response.status_code == 200
    assert "immutable" in response.headers["cache-control"]


def test_service_worker_is_revalidated(client: TestClient) -> None:
    assert client.get("/sw.js").headers["cache-control"] == "no-cache"


def test_path_traversal_serves_index(client: TestClient) -> None:
    response = client.get("/..%2F..%2Fetc%2Fpasswd")
    assert "<title>index</title>" in response.text


def test_head_is_answered_like_get(client: TestClient) -> None:
    for path in ("/", "/note/123", "/assets/app-abc123.js", "/api/v1/health"):
        assert client.head(path).status_code == 200, path


def test_missing_assets_are_not_found(client: TestClient) -> None:
    response = client.get("/assets/app-gone.js")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
