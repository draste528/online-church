from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database connections
    POSTGRES_USER: str = "church_admin"
    POSTGRES_PASSWORD: str = "church_secret"
    POSTGRES_HOST: str = "postgres_dwh"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "church_dwh"

    # API Configuration
    ANALYTICS_API_PORT: int = 8000
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    # Time zone used to bucket donations by hour of day (falls back to UTC if the name is unknown).
    ANALYTICS_TIMEZONE: str = "Europe/Moscow"
    # Browser origins allowed to call the API, comma-separated; "*" allows everything.
    CORS_ORIGINS: str = "*"

    @property
    def database_url(self) -> str:
        # The driver is named explicitly: SQLAlchemy 2.1 would otherwise look for psycopg 3 instead of psycopg2.
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def safe_database_url(self) -> str:
        """The connection URL without the password, for logs."""
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:***@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
