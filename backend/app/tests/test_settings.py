import pytest
from pydantic import ValidationError

from app.config.settings import Settings

BASE_SETTINGS = {
    "database_url": ("postgresql://user:pass@localhost/test_db"),
    "openai_api_key": "test-api-key",
    "openai_model": "test-model",
}


def make_settings(**overrides) -> Settings:
    values = {
        **BASE_SETTINGS,
        **overrides,
    }

    return Settings(
        _env_file=None,
        **values,
    )


def test_valid_settings():
    settings = make_settings()

    assert settings.environment == "development"
    assert settings.max_agent_steps == 5


def test_blank_openai_model_rejected():
    with pytest.raises(ValidationError):
        make_settings(
            openai_model="",
        )


def test_invalid_environment_rejected():
    with pytest.raises(ValidationError):
        make_settings(
            environment="staginggg",
        )


def test_invalid_agent_step_limit_rejected():
    with pytest.raises(ValidationError):
        make_settings(
            max_agent_steps=0,
        )


def test_log_level_normalized():
    settings = make_settings(
        log_level="debug",
    )

    assert settings.log_level == "DEBUG"


def test_cors_origins_parsed():
    settings = make_settings(
        cors_origins=("http://localhost:5173," "https://example.com"),
    )

    assert settings.parsed_cors_origins == [
        "http://localhost:5173",
        "https://example.com",
    ]
