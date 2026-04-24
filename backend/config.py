from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional

class Settings(BaseSettings):
    # Required API keys
    openai_api_key: str

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

    # Agent settings
    agent_recursion_limit: int = 100  # Max LangGraph ReAct loop steps per agent invocation

    # Layer-4 orchestrator response-quality judge (see plan: orchestration error handling)
    # All env-driven via .env; empty defaults here so config is explicit in ops.
    judge_llm_provider: str = ""        # empty → falls back to default_llm_provider
    judge_llm_model: str = ""           # e.g. "gpt-5-mini"; empty → judge disabled (falls open)
    judge_timeout_seconds: int = 10
    judge_enabled: bool = True          # kill-switch for the whole layer
    judge_highlight_enabled: bool = True  # mark meaningful numbers with ==...== for frontend orange rendering

    # Database
    database_url: str = "postgresql://thebingo_user:thebingo_password@localhost:5432/thebingo"
    database_url_direct: Optional[str] = None  # Direct connection for migrations (bypasses Supabase connection pooler)

    # Schema storage
    schemas_dir: str = "data/schemas"

# Database password encryption
    # Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
    db_encryption_key: str = "REPLACE_WITH_FERNET_KEY_44_CHARS"

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

    # Chat file upload settings
    chat_file_max_size: int = 52_428_800  # 50MB
    chat_file_max_count: int = 5
    chat_file_ttl_seconds: int = 3600
    chat_file_csv_max_rows: int = 100
    chat_file_pdf_max_pages: int = 10
    chat_file_text_max_chars: int = 50_000

    # Dataset profiling
    profile_sample_rows: int = 5
    profile_max_categories: int = 30
    profile_correlation_threshold: float = 0.1
    profile_max_correlation_columns: int = 20
    profile_outlier_std: float = 3.0
    profile_max_columns: int = 50

    # Dataset upload settings
    dataset_max_file_size: int = 52_428_800  # 50MB
    dataset_max_rows: int = 500_000
    dataset_cache_dir: str = "/tmp/gruda_datasets"

    # DigitalOcean Spaces (S3-compatible object storage)
    do_spaces_bucket: str = "ai365"
    do_spaces_base_path: str = "bingo/dev"  # override per environment via DO_SPACES_BASE_PATH
    do_spaces_endpoint: str = "https://sgp1.digitaloceanspaces.com"
    do_spaces_region: str = "sgp1"
    do_spaces_key_id: Optional[str] = None
    do_spaces_secret_key: Optional[str] = None

    # Server settings
    cors_allowed_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:5173"
    app_version: str = "0.1.0"
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # Logging
    log_level: str = "INFO"

    # Query guardrails
    max_query_rows: int = 5000
    query_timeout_ms: int = 120000

    # SSO Authentication
    sso_base_url: str = "https://sso.thebingo.ai"
    sso_publishable_key: str = "Bingo-Community"   # app name (community) or pk_* key (enterprise)
    sso_secret_key: str = ""           # sk_* key for backend
    sso_token_cache_ttl: int = 300     # seconds (5 min)
    sso_webhook_secret: str = ""       # webhook signature verification
    sso_redis_url: str = "redis://localhost:6379/3"  # DB 3: SSO token cache

    # Feature flags
    enable_governance: bool = False
    agent_mesh_enabled: bool = False

    # Agent mesh settings (Redis DB 4)
    agent_mesh_redis_url: str = "redis://localhost:6379/4"

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(cls, v):
        if not 0.0 <= v <= 0.5:
            raise ValueError("chunk_overlap must be between 0.0 and 0.5")
        return v

    @field_validator("default_llm_provider")
    @classmethod
    def validate_provider(cls, v):
        valid = ("openai", "anthropic", "ollama")
        if v not in valid:
            raise ValueError(f"provider must be one of: {', '.join(valid)}")
        return v


    @field_validator("db_encryption_key")
    @classmethod
    def validate_encryption_key(cls, v):
        """Prevent use of placeholder encryption key."""
        if v == "REPLACE_WITH_FERNET_KEY_44_CHARS":
            raise ValueError(
                "DB_ENCRYPTION_KEY must be set to a valid Fernet key. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore unknown env vars (e.g. JWT_SECRET_KEY from old .env files)
    )

# Singleton instance
settings = Settings()
