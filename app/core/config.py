from typing import Optional
from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Configuration settings for the application, loaded from .env file and environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    POSTGRES_DB: str

    @property
    def POSTGRES_CONNECTION_STRING(self) -> str:
        """
        Return PostgreSQL connection string for checkpointer (psycopg sync style).
        
        Args:
            None

        Returns:
            str: PostgreSQL connection string.
        """
        return (
            f"postgresql://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:"
            f"{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        """
        Return the SQLAlchemy async PostgreSQL connection URL.
        
        Args:
            None

        Returns:
            str: SQLAlchemy async PostgreSQL connection URL.
        """
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:"
            f"{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    MONGO_URI: str
    MONGO_DB: str

    PROJECT_NAME: str
    API_STR: str
    PROJECT_VERSION: str
    PROJECT_DESCRIPTION: str

    ACCESS_TOKEN_SECRET_KEY: str
    REFRESH_TOKEN_SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_HOURS: int
    MAX_SESSIONS_PER_USER: int = 3
    PASSWORD_RESET_SECRET_KEY: str

    SUPER_ADMIN_NAME: str
    SUPER_ADMIN_EMAIL: str
    SUPER_ADMIN_USERNAME: str
    SUPER_ADMIN_PASSWORD: str

    HUB_LATITUDE: float
    HUB_LONGITUDE: float

    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: EmailStr
    MAIL_FROM_NAME: str
    MAIL_SERVER: str
    MAIL_PORT: int
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

    AZURE_STORAGE_CONNECTION_STRING: str
    PROFILE_CONTAINER_NAME: str
    LICENSE_CONTAINER_NAME: str
    AADHAAR_CONTAINER_NAME: str
    INVENTORY_CONTAINER_NAME: str
    BACKUP_CONTAINER_NAME: str
    BOOKING_CONTAINER_NAME: str

    GOOGLE_GEOCODING_API_KEY: str

    FRONTEND_URL: str

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int

    RATE_LIMIT_REQUESTS_PER_MINUTE: int
    RATE_LIMIT_REQUESTS_PER_HOUR: int
    RATE_LIMIT_REQUESTS_PER_DAY: int

    # Assistant Settings

    OPENAI_API_KEY: str
    OPENAI_API_BASE_URL: str = "https://Fyra.im/v1"
    OPENAI_MODEL: str = "gpt-oss-20b"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 1000
    GROQ_API_KEY: str
    GROQ_MODEL: str

    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    SEMANTIC_BREAKPOINT_TYPE: str = "percentile"
    SEMANTIC_BREAKPOINT_THRESHOLD: float = 0.95
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 100

    TOP_K_RESULTS: int = 10
    SIMILARITY_THRESHOLD: float = 0.25
    RERANK_TOP_N: int = 5

    RECOMMENDATION_BATCH_SIZE: int = 100
    RECOMMENDATION_LIMIT: int = 5
    RECOMMENDATION_DAYS_LOOKBACK: int = 90

    MAX_HISTORY_MESSAGES: int = 10
    CONTEXT_WINDOW_SIZE: int = 4096

    LANGSMITH_TRACING: str = "true"
    LANGSMITH_API_KEY: Optional[str] = None
    LANGSMITH_PROJECT: str = "crs-rag-agent"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"

    REDIS_CACHE_TTL: int = 3600
    ENABLE_CACHE: bool = True

    ENABLE_MEMORY: bool = True
    STREAMING_ENABLED: bool = True


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()
