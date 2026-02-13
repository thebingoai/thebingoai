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
    default_llm_temperature: float = 0.7

    # LLM Provider-specific settings
    openai_default_model: str = "gpt-4o"
    anthropic_default_model: str = "claude-sonnet-4-20250514"
    anthropic_default_max_tokens: int = 4096
    ollama_default_model: str = "llama3.2"
    ollama_request_timeout: float = 120.0

    # Chunking settings
    chunk_size: int = 512
    chunk_overlap: float = 0.2

    # Embedding settings
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072
    embedding_batch_size: int = 100
    embedding_max_retries: int = 3

    # Pinecone settings (additional)
    pinecone_upsert_batch_size: int = 100
    pinecone_similarity_metric: str = "cosine"
    pinecone_cloud_provider: str = "aws"

    # Qdrant settings (for memory system)
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_documents_collection: str = "documents"
    qdrant_memories_collection: str = "memories"
    qdrant_vector_size: int = 3072  # text-embedding-3-large

    # RAG settings
    rag_default_top_k: int = 5
    rag_context_score_threshold: float = 0.5
    rag_conversation_history_messages: int = 6

    # Database
    database_url: str = "postgresql://llm_user:llm_password@localhost:5432/llm_cli"

    # Schema storage
    schemas_dir: str = "data/schemas"

    # JWT Authentication
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440  # 24 hours

    # Redis/Celery settings
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_url: str = "redis://localhost:6379/2"
    job_ttl_seconds: int = 604800  # 7 days
    conversation_ttl_seconds: int = 604800  # 7 days

    # Celery task settings
    celery_task_time_limit: int = 3600
    celery_max_retries: int = 3
    celery_retry_base_countdown: int = 60

    # Async processing thresholds
    async_file_size_threshold: int = 100_000  # 100KB
    async_chunk_count_threshold: int = 20
    upload_max_file_size: int = 52428800  # 50MB

    # Server settings
    cors_allowed_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:5173"
    app_version: str = "0.1.0"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

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
