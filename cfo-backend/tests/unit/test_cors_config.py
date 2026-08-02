from app.config import Settings


def test_cors_allowed_origins_env(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", "https://app.example.com,https://admin.example.com"
    )
    settings = Settings()
    assert settings.CORS_ALLOWED_ORIGINS == (
        "https://app.example.com,https://admin.example.com"
    )


def test_cors_legacy_alias_still_works(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://legacy.example.com")
    settings = Settings()
    assert settings.CORS_ALLOWED_ORIGINS == "https://legacy.example.com"


def test_cors_new_name_wins_over_legacy(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://new.example.com")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://legacy.example.com")
    settings = Settings()
    assert settings.CORS_ALLOWED_ORIGINS == "https://new.example.com"
