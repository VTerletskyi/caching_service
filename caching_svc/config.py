from pydantic import BaseModel, NonNegativeFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    url: str = "postgresql+asyncpg://caching_user:caching_password@localhost:5441/caching_db"
    echo: bool = False
    # asyncpg connections are bound to the event loop that opened them; the test env disables
    # pooling so a connection never outlives the loop of the test/fixture that created it.
    use_null_pool: bool = False


class WebsiteAppSettings(BaseModel):
    title: str = "Caching Service"
    description: str = "Generates payloads from transformed strings and caches transformations"
    version: str = "0.1.0"
    docs_url: str = "/docs"

    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False


class ApplicationsSettings(BaseModel):
    website: WebsiteAppSettings = WebsiteAppSettings()


class TransformerConfig(BaseModel):
    delay_seconds: NonNegativeFloat = 0.5
    # Upper bound of in-flight calls to the external service for a single payload request.
    max_concurrency: PositiveInt = 10


class Settings(BaseSettings):
    database: DatabaseConfig = DatabaseConfig()
    applications: ApplicationsSettings = ApplicationsSettings()
    transformer: TransformerConfig = TransformerConfig()

    log_level: str = "INFO"
    service_name: str = "caching_svc"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()
