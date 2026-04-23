from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "changeme-in-production-use-env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    MONITORING_API_KEY: str = "skillbridge-monitor-secret-2024"
    MONITORING_TOKEN_EXPIRE_MINUTES: int = 60  # 1 hour

    class Config:
        env_file = ".env"


settings = Settings()
