from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    # Twitter API Credentials
    TWITTER_API_KEY: str
    TWITTER_API_SECRET: str
    TWITTER_ACCESS_TOKEN: str
    TWITTER_ACCESS_TOKEN_SECRET: str
    TWITTER_BEARER_TOKEN: str

    # Application Settings
    DATABASE_URL: str = 'sqlite:///./data/twittertools.db'
    API_HOST: str = '127.0.0.1'
    API_PORT: int = 8000
    DEBUG: bool = True
    FRONTEND_URL: str = 'http://localhost:5173'

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

@lru_cache
def get_settings():
    return Settings() 