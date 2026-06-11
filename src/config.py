from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    base_url: str = "https://www.saucedemo.com"
    headless: bool = True
    heal_confidence_threshold: float = 0.8
    locator_timeout_ms: int = 5000


settings = Settings()
