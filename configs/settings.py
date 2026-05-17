"""
Central application settings loaded from environment variables / .env file.
All subsystems import from here — never read os.environ directly elsewhere.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = Field(default="localhost", alias="POSTGRES_HOST")
    port: int = Field(default=5432, alias="POSTGRES_PORT")
    name: str = Field(default="ats_db", alias="POSTGRES_DB")
    user: str = Field(default="ats_user", alias="POSTGRES_USER")
    password: str = Field(default="ats_password", alias="POSTGRES_PASSWORD")
    url: str = Field(
        default="postgresql+asyncpg://ats_user:ats_password@localhost:5432/ats_db",
        alias="DATABASE_URL",
    )


class ChromaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = Field(default="localhost", alias="CHROMA_HOST")
    port: int = Field(default=8001, alias="CHROMA_PORT")
    token: str = Field(default="ats-chroma-token", alias="CHROMA_TOKEN")
    collection_candidates: str = Field(default="ats_candidates", alias="CHROMA_COLLECTION_CANDIDATES")
    collection_resumes: str = Field(default="ats_resumes", alias="CHROMA_COLLECTION_RESUMES")
    collection_feedback: str = Field(default="ats_feedback", alias="CHROMA_COLLECTION_FEEDBACK")
    collection_interventions: str = Field(default="ats_interventions", alias="CHROMA_COLLECTION_INTERVENTIONS")

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    # Model tiers match the architecture's cost-optimised routing
    model_coordinator: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL_COORDINATOR")
    model_insight: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL_INSIGHT")
    model_support: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL_SUPPORT")
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL",
    )
    embedding_dimension: int = Field(default=384, alias="EMBEDDING_DIMENSION")


class LangfuseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    public_key: str = Field(default="", alias="LANGFUSE_PUBLIC_KEY")
    secret_key: str = Field(default="", alias="LANGFUSE_SECRET_KEY")
    host: str = Field(default="https://cloud.langfuse.com", alias="LANGFUSE_HOST")
    enabled: bool = Field(default=False, alias="LANGFUSE_ENABLED")


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_url: str = Field(default="http://localhost:9000", alias="MCP_SERVICE_URL")
    service_token: str = Field(default="", alias="MCP_SERVICE_TOKEN")
    timeout_seconds: int = Field(default=10, alias="MCP_TIMEOUT_SECONDS")


class SmtpSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    port: int = Field(default=587, alias="SMTP_PORT")
    user: str = Field(default="", alias="SMTP_USER")
    password: str = Field(default="", alias="SMTP_PASSWORD")
    from_address: str = Field(default="", alias="SMTP_FROM")
    starttls: bool = Field(default=True, alias="SMTP_STARTTLS")


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = Field(default="localhost", alias="REDIS_HOST")
    port: int = Field(default=6379, alias="REDIS_PORT")
    url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8080, alias="APP_PORT")
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    secret_key: str = Field(default="changeme", alias="SECRET_KEY")

    database: DatabaseSettings = DatabaseSettings()
    chroma: ChromaSettings = ChromaSettings()
    llm: LLMSettings = LLMSettings()
    mcp: MCPSettings = MCPSettings()
    redis: RedisSettings = RedisSettings()
    langfuse: LangfuseSettings = LangfuseSettings()
    smtp: SmtpSettings = SmtpSettings()

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


# Singleton — import and use anywhere in the codebase
settings = Settings()
