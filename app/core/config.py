from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://payments:payments@postgres:5432/payments"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    api_key: str = "change-me"
    webhook_timeout: float = 5.0
    outbox_poll_interval: float = 1.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
