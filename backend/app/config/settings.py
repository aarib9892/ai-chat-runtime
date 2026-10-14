from functools import lru_cache

from pydantic import (
    Field,
    field_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------------------------------
    # Environment
    # ---------------------------------

    environment: str = "development"
    log_level: str = "INFO"

    # ---------------------------------
    # Database
    # ---------------------------------

    database_url: str

    # ---------------------------------
    # OpenAI
    # ---------------------------------

    openai_api_key: str
    openai_model: str

    openai_input_cost_per_1m_usd: float = Field(
        default=0,
        ge=0,
    )

    openai_output_cost_per_1m_usd: float = Field(
        default=0,
        ge=0,
    )

    # ---------------------------------
    # Context management
    # ---------------------------------

    max_output_tokens: int = Field(
        default=2000,
        gt=0,
    )

    app_max_input_tokens: int = Field(
        default=8000,
        gt=0,
    )

    safety_margin_tokens: int = Field(
        default=500,
        ge=0,
    )

    token_estimation_buffer: float = Field(
        default=0.05,
        ge=0,
        lt=1,
    )

    summary_max_output_tokens: int = Field(
        default=800,
        gt=0,
    )

    # ---------------------------------
    # Embeddings / RAG
    # ---------------------------------

    embedding_model: str = "text-embedding-3-small"

    embedding_dimensions: int = Field(
        default=1536,
        gt=0,
    )

    # ---------------------------------
    # Agent safeguards
    # ---------------------------------

    max_agent_steps: int = Field(
        default=5,
        ge=1,
        le=20,
    )

    max_agent_tool_calls: int = Field(
        default=8,
        ge=1,
        le=50,
    )

    max_identical_tool_calls: int = Field(
        default=2,
        ge=1,
        le=10,
    )

    # ---------------------------------
    # Concurrency
    # ---------------------------------

    max_concurrent_agent_runs: int = Field(
        default=5,
        ge=1,
    )

    agent_queue_timeout_seconds: float = Field(
        default=5.0,
        gt=0,
    )

    # ---------------------------------
    # Rate limiting
    # ---------------------------------

    ask_rate_limit: int = Field(
        default=20,
        ge=1,
    )

    ask_rate_window_seconds: float = Field(
        default=60,
        gt=0,
    )

    # ---------------------------------
    # CORS
    # ---------------------------------

    cors_origins: str = "http://localhost:5173"

    # ---------------------------------
    # Validators
    # ---------------------------------

    @field_validator("environment")
    @classmethod
    def validate_environment(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip().lower()

        allowed = {
            "development",
            "test",
            "production",
        }

        if normalized not in allowed:
            raise ValueError("environment must be " "development, test or production")

        return normalized

    @field_validator(
        "database_url",
        "openai_api_key",
        "openai_model",
        "embedding_model",
    )
    @classmethod
    def must_not_be_blank(
        cls,
        value: str,
    ) -> str:
        value = value.strip()

        if not value:
            raise ValueError("value must not be blank")

        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(
        cls,
        value: str,
    ) -> str:
        value = value.strip().upper()

        allowed = {
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
        }

        if value not in allowed:
            raise ValueError("Invalid log level")

        return value

    # ---------------------------------
    # Derived properties
    # ---------------------------------

    @property
    def parsed_cors_origins(
        self,
    ) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    @property
    def is_production(
        self,
    ) -> bool:
        return self.environment == "production"

    @property
    def is_development(
        self,
    ) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
