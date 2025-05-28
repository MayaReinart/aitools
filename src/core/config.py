from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field(default=..., validation_alias="OPENAI_API_KEY")
    ENV: str = Field(default=..., validation_alias="ENV")
    LOG_LEVEL: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    REDIS_URL: str = Field(
        default="redis://localhost:6379", validation_alias="REDIS_URL"
    )
    S3_BUCKET_NAME: str | None = Field(default=None, validation_alias="S3_BUCKET_NAME")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
