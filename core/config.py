import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "sjn-demo"
    API_V1_STR: str = "/api/v1"
    
    # Environment
    PYTHON_ENV: str = os.getenv("PYTHON_ENV", "development")
    DEPLOYE_PLATFORM: str = os.getenv("DEPLOYE_PLATFORM", "vps")

    @property
    def is_production(self) -> bool:
        return self.PYTHON_ENV.lower() == "production"

    ARGON2_RAM_SIZE: int = os.getenv("ARGON2_RAM_SIZE")

    PAPPER: str = os.getenv("PAPPER")

    RENDER_SECRET_HEADER_NAME: str = os.getenv("RENDER_SECRET_HEADER_NAME")
    SECRET_HEADER_VALUE: str = os.getenv("SECRET_HEADER_VALUE")

    IS_REAL: bool = os.getenv("IS_REAL", "False").lower() == "true"
    
    # Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "fallback-secret-key-at-least-32-chars-long")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 11520))
    
    # Engine 1: Rate Limiter (Local Redis)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    
    # Engine 2: Cache (Upstash Redis REST)
    UPSTASH_REDIS_REST_URL: str = os.getenv("UPSTASH_REDIS_REST_URL")
    UPSTASH_REDIS_REST_TOKEN: str = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    
    # Engine 3: Celery (CloudAMQP)
    CELERY_WORKER_BROKER_URL: str = os.getenv("CELERY_WORKER_BROKER_URL")
    
    # Database
    # MONGODB_URL: str = os.getenv("MONGODB_URL")
    # MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "sjn_demo_db")

    TIDB_HOST: str = os.getenv("TIDB_HOST")
    TIDB_PORT: int = os.getenv("TIDB_PORT")
    TIDB_USER: str = os.getenv("TIDB_USER")
    TIDB_PASSWORD: str = os.getenv("TIDB_PASSWORD")
    TIDB_DATABASE: str = os.getenv("TIDB_DATABASE")

    TIDB_CA_CERT: str = "db/certs/tidb.pem"
    
    # Sentry
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")

    # Loki Configuration
    LOKI_URL: str | None = os.getenv("LOKI_URL", None)
    LOKI_USERNAME: str | None = os.getenv("LOKI_USERNAME", None)
    LOKI_PASSWORD: str | None = os.getenv("LOKI_PASSWORD", None)

    POSTHOG_PROJECT_KEY: str = os.getenv("POSTHOG_PROJECT_KEY", "")

    #Cloudflare TURNSTILE
    CLOUDFLARE_VERIFY_URL: str = os.getenv("CLOUDFLARE_VERIFY_URL", "")
    TURNSTILE_SECRET_KEY: str = os.getenv("TURNSTILE_SECRET_KEY", "")

    # CORS Configuration
    ALLOWED_ORIGINS: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    # Cookie Security
    # In development (HTTP): Must be False to allow cookies on localhost
    # In production (HTTPS): Must be True for security
    COOKIE_SAMESITE: str = os.getenv("COOKIE_SAMESITE", "lax") # "strict", "lax", or "none"
    _COOKIE_SECURE_ENV = os.getenv("COOKIE_SECURE", None)
    
    @property
    def COOKIE_SECURE(self) -> bool:
        """
        Determine if cookies should be Secure flag.
        - Explicit env var takes precedence
        - Otherwise: True for production, False for development
        - CRITICAL: Over HTTP, Secure cookies are rejected by browsers
        """
        if self._COOKIE_SECURE_ENV is not None:
            return self._COOKIE_SECURE_ENV.lower() == "true"
        # Default: True for production (HTTPS), False for development (HTTP)
        return self.is_production

    # ─── Razorpay Payment Gateway 
    RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET")
    RAZORPAY_WEBHOOK_SECRET: str = os.getenv("RAZORPAY_WEBHOOK_SECRET")

    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    
    @property
    def BACKEND_CORS_ORIGINS(self) -> list[str]:
        raw = self.ALLOWED_ORIGINS or "http://localhost:5173,http://127.0.0.1:5173"
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def ACCESS_TOKEN_COOKIE_NAME(self) -> str:
        # __Host- prefix requires Secure=True (HTTPS only).
        # In development (HTTP), use a plain name so Postman/browsers accept it.
        # PRODUCTION: __Host-access_token
        return "__Host-access_token" if self.COOKIE_SECURE else "access_token"

    @property
    def REFRESH_TOKEN_COOKIE_NAME(self) -> str:
        # PRODUCTION: __Host-refresh_token
        return "__Host-refresh_token" if self.COOKIE_SECURE else "refresh_token"

    RENDER_SECRET_HEADER_NAME: str = os.getenv("RENDER_SECRET_HEADER_NAME", "shgdjhgsdhjgsdhjsd")
    SECRET_HEADER_VALUE: str = os.getenv("SECRET_HEADER_VALUE", "sgdyutsudtyusghjgshygs")

    




    
    #==================== Firebase Cradential ========================
    PROJECT_ID: str = os.getenv("PROJECT_ID")
    PRIVATE_KEY_ID: str = os.getenv("PRIVATE_KEY_ID")
    PRIVATE_KEY: str = os.getenv("PRIVATE_KEY")
    CLIENT_EMAIL: str = os.getenv("CLIENT_EMAIL")
    CLIENT_ID: str = os.getenv("CLIENT_ID")
    AUTH_URI: str = os.getenv("AUTH_URI")
    TOKEN_URI: str = os.getenv("TOKEN_URI")
    AUTH_PROVIDER_X509_CERT_URL: str = os.getenv("AUTH_PROVIDER_X509_CERT_URL")
    CLIENT_X509_CERT_URL: str = os.getenv("CLIENT_X509_CERT_URL")
    UNIVERSE_DOMAIN: str = os.getenv("UNIVERSE_DOMAIN")

    class Config:
        case_sensitive = True

    # Cloudinary cradentials
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET")


settings = Settings()
