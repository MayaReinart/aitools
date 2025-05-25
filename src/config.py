from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
