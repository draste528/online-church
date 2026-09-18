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

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
