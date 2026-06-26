from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://oms_user:oms_dev_password@localhost:5433/flow_ops_tms"
    OMS_DATABASE_URL: str = "postgresql+asyncpg://oms_user:oms_dev_password@localhost:5433/flow_ops_oms"
    OMS_API_URL: str = "http://localhost:8000/api/v1"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"

settings = Settings()
