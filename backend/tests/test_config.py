from pathlib import Path

import pytest

from app.config import ConfigError, Settings, load_settings


@pytest.fixture(autouse=True)
def _data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_DATA_DIR", str(tmp_path / "data"))


def test_base_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_BASE_URL", raising=False)
    with pytest.raises(ConfigError, match="APP_BASE_URL: is required"):
        load_settings()


def test_base_url_must_be_absolute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "notes.example.com")
    with pytest.raises(ConfigError, match="APP_BASE_URL"):
        load_settings()


def test_base_url_trailing_slash_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://notes.example.com/")
    settings = load_settings()
    assert settings.base_url == "https://notes.example.com"
    assert settings.secure_cookies


def test_password_login_off_requires_oidc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://notes.example.com")
    monkeypatch.setenv("APP_PASSWORD_LOGIN_ENABLED", "false")
    with pytest.raises(ConfigError, match="requires OIDC"):
        load_settings()
    monkeypatch.setenv("APP_OIDC_DISCOVERY_URL", "https://id.example.com/.well-known/openid-configuration")
    monkeypatch.setenv("APP_OIDC_CLIENT_ID", "notes")
    monkeypatch.setenv("APP_OIDC_CLIENT_SECRET", "secret")
    assert load_settings().oidc_enabled


def test_trusted_proxies_are_comma_separated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://notes.example.com")
    monkeypatch.setenv("APP_TRUSTED_PROXIES", "10.0.0.1, 172.16.0.0/12")
    assert load_settings().trusted_proxies == ["10.0.0.1", "172.16.0.0/12"]


def test_negative_numbers_name_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://notes.example.com")
    monkeypatch.setenv("APP_TRASH_RETENTION_DAYS", "-1")
    with pytest.raises(ConfigError, match="APP_TRASH_RETENTION_DAYS: must not be negative"):
        load_settings()


@pytest.mark.parametrize("name", ["APP_MAX_IMAGE_MB", "APP_SESSION_DAYS"])
def test_limits_must_be_positive(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://notes.example.com")
    monkeypatch.setenv(name, "0")
    with pytest.raises(ConfigError, match=f"{name}: must be at least 1"):
        load_settings()


def test_every_problem_is_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://notes.example.com")
    monkeypatch.setenv("APP_MAX_IMAGE_MB", "ten")
    monkeypatch.setenv("APP_LOG_LEVEL", "loud")
    with pytest.raises(ConfigError, match=r"(?s)APP_MAX_IMAGE_MB: .*integer.*APP_LOG_LEVEL: "):
        load_settings()


def test_partial_oidc_names_what_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://notes.example.com")
    monkeypatch.setenv("APP_OIDC_CLIENT_ID", "notes")
    with pytest.raises(ConfigError, match="missing APP_OIDC_DISCOVERY_URL, APP_OIDC_CLIENT_SECRET"):
        load_settings()


def test_discovery_url_must_be_a_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://notes.example.com")
    monkeypatch.setenv("APP_OIDC_DISCOVERY_URL", "id.example.com")
    monkeypatch.setenv("APP_OIDC_CLIENT_ID", "notes")
    monkeypatch.setenv("APP_OIDC_CLIENT_SECRET", "secret")
    with pytest.raises(ConfigError, match="APP_OIDC_DISCOVERY_URL: must be an absolute"):
        load_settings()


def test_trusted_proxies_must_be_addresses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://notes.example.com")
    monkeypatch.setenv("APP_TRUSTED_PROXIES", "10.0.0.1, proxy.local")
    with pytest.raises(ConfigError, match=r"APP_TRUSTED_PROXIES: 'proxy\.local' is not an IP address"):
        load_settings()


def test_secret_key_must_not_be_short(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://notes.example.com")
    monkeypatch.setenv("APP_SECRET_KEY", "hunter2")
    with pytest.raises(ConfigError, match="APP_SECRET_KEY: must be at least 32 characters"):
        load_settings()


def test_data_dir_must_be_writable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APP_BASE_URL", "https://notes.example.com")
    blocked = tmp_path / "file"
    blocked.write_text("")
    monkeypatch.setenv("APP_DATA_DIR", str(blocked / "data"))
    with pytest.raises(ConfigError, match="APP_DATA_DIR: cannot write to"):
        load_settings()


def test_secret_key_is_generated_once(tmp_path: Path) -> None:
    first = Settings(base_url="http://x", data_dir=tmp_path).resolved_secret_key
    second = Settings(base_url="http://x", data_dir=tmp_path).resolved_secret_key
    assert first == second
    assert (tmp_path / "secret.key").stat().st_mode & 0o777 == 0o600


def test_configured_secret_key_wins(tmp_path: Path) -> None:
    key = "configured-" + "k" * 32
    settings = Settings(base_url="http://x", data_dir=tmp_path, secret_key=key)
    assert settings.resolved_secret_key == key
    assert not (tmp_path / "secret.key").exists()
