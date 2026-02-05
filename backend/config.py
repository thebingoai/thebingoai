from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional

class Settings(BaseSettings):
    # Required API keys
    openai_api_key: str
    pinecone_api_key: str

    # Pinecone settings
    pinecone_index_name: str = "llm-md-index"
    pinecone_environment: str = "us-east-1"

    # Optional LLM providers
    anthropic_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"

    # Default LLM settings
    default_llm_provider: str = "openai"
    default_llm_model: Optional[str] = None

    # Chunking settings
    chunk_size: int = 512
    chunk_overlap: float = 0.2

    # Embedding settings
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072

    # Redis/Celery settings
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_url: str = "redis://localhost:6379/2"

    # Async processing thresholds
    async_file_size_threshold: int = 100_000  # 100KB
    async_chunk_count_threshold: int = 20

    # Logging
    log_level: str = "INFO"

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(cls, v):
        if not 0.0 <= v <= 0.5:
            raise ValueError("chunk_overlap must be between 0.0 and 0.5")
        return v

    @field_validator("default_llm_provider")
    @classmethod
    def validate_provider(cls, v):
        if v not in ("openai", "anthropic", "ollama"):
            raise ValueError("provider must be openai, anthropic, or ollama")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Singleton instance
settings = Settings()
