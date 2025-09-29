try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "Starline Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # Database Settings
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "starline")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "@DM1N")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "starline_db")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")

    # Email Settings
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@starline.com")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:4200")

    # AWS Settings
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_KEY", "")
    AWS_S3_BUCKET: str = os.getenv("AWS_S3_BUCKET", "starline")
    AWS_REGION: str = os.getenv("AWS_REGION", "eu-west-2")
    CLOUDFRONT_URL: str = os.getenv("CLOUDFRONT_URL", "")

    # Redis Settings
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)

    # Security Settings
    BCRYPT_ROUNDS: int = 12
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int = 48
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 48
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 30

    # Default Admin Settings
    DEFAULT_ADMIN_EMAIL: str = os.getenv("DEFAULT_ADMIN_EMAIL", "support@starline.com")
    DEFAULT_ADMIN_USERNAME: str = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin123!!")
    DEFAULT_ADMIN_FULL_NAME: str = os.getenv("DEFAULT_ADMIN_FULL_NAME", "Admin")

    # CORS Settings
    BACKEND_CORS_ORIGINS: list = ["*"]

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Session Settings
    SESSION_EXPIRE_MINUTES: int = 30
    REMEMBER_ME_DAYS: int = 30

    # OTP Settings
    OTP_EXPIRE_MINUTES: int = 10
    OTP_LENGTH: int = 6

    # File Upload Settings
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "10"))

    class Config:
        case_sensitive = True

settings = Settings()