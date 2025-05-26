from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field(env="OPENAI_API_KEY")
    ENV: str = Field(env="ENV")
    LOG_LEVEL: str = Field(env="LOG_LEVEL")
    REDIS_URL: str = Field(env="REDIS_URL")
    S3_BUCKET_NAME: str = Field(env="S3_BUCKET_NAME")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
