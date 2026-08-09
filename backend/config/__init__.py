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
    anthropic_default_model: str = "claude-sonnet-4-6"
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
    # Chat turns replay history into the prompt. Unbounded, this grew until the
    # provider's context limit rejected the turn outright, bricking that user's
    # chat until they reset it — permanent conversations cannot be deleted.
    chat_history_max_messages: int = 100
    # A row cap alone does not bound the prompt: ChatRequest allows 50k chars per
    # message, so 100 rows is up to 5M chars — well past any context window. A BI
    # chat gets pasted CSVs and log dumps, so this is reachable in ordinary use.
    # Chars, not tokens, on purpose: no per-provider tokenizer to keep in sync,
    # and the bound only has to be safe, not exact. ~4 chars/token.
    chat_history_max_chars: int = 200_000
    # The daily memory generator summarises history instead of replaying it into
    # a turn, so it wants a wider window than a chat turn and keeps the messages
    # before a context reset. Still bounded — it concatenates across every
    # conversation of the day into one prompt.
    memory_history_max_messages: int = 500
    # And the same reason `chat_history_max_chars` exists: 500 rows is 500 x 50k
    # chars in the worst case. Wider than a chat turn's budget because a day's
    # digest legitimately spans more conversations.
    memory_history_max_chars: int = 400_000

    # Agent settings
    agent_recursion_limit: int = 100  # Max LangGraph ReAct loop steps per agent invocation
    data_agent_query_budget: int = 5  # Soft cap on execute_query calls per data_agent run before "summarize now" is injected

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
    db_pool_size: int = 10      # client-side connections kept warm per process
    db_max_overflow: int = 20   # extra connections allowed beyond pool_size under burst
    db_pool_timeout: int = 5    # seconds to wait for a free slot before raising TimeoutError
    db_connect_timeout: int = 5 # seconds libpq waits to establish a connection (see database/session.py)
    db_pool_trace: bool = False           # log pool pressure (see database/session.py)
    db_pool_trace_slow_ms: int = 1000     # warn when a checkout is held at least this long

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

    # Pipelines — default cron applied to auto-created MySQL pipelines at connect
    default_sql_pipeline_cron: str = "0 2 * * *"  # daily 02:00 (pipeline timezone)
    # Incremental first-run lower bound: today − N days (start of day, UTC).
    # Applied as the dlt incremental cursor's `initial_value` so the first
    # ingest pulls from T−N forward instead of the source's beginning.
    first_ingest_lookback_days: int = 1
    # Incremental cursor upper-bound cutoff, in whole days back from the start
    # of today UTC. 1 = T-1 (exclude same-day partials); 2 = T-2; 0 = include
    # today. Applied per incremental pipeline in `connectors.sql_dlt`.
    incremental_cutoff_days: int = 1

    # Watermark classifier — picks the per-table incremental cursor column from
    # the live schema. Empty model/provider → deterministic-only fallback (no
    # LLM call); both set → batched LLM classification with deterministic
    # fallback on error / low confidence. See services/watermark_classifier.py.
    watermark_classifier_provider: str = ""  # openai | anthropic | ollama | ""
    watermark_classifier_model: str = ""     # e.g. gpt-4o-mini; "" disables

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
    dataset_cache_dir: str = "/tmp/gruda_datasets"

    # DigitalOcean Spaces (S3-compatible object storage)
    do_spaces_bucket: str = "ai365"
    do_spaces_base_path: str = "bingo/dev"  # override per environment via DO_SPACES_BASE_PATH
    do_spaces_endpoint: str = "https://sgp1.digitaloceanspaces.com"
    do_spaces_region: str = "sgp1"
    do_spaces_key_id: Optional[str] = None
    do_spaces_secret_key: Optional[str] = None

    # DataPlane (Phase 1)
    data_plane_local_root: str = "/data/data_plane"

    # DataPlane lockdown (Shape A): when true, get_default_plane() raises
    # NoPlaneProvisionedError instead of falling back to LocalFilesystem, and
    # any local_filesystem rows raise LocalPlaneUnderLockdownError on access.
    # Per-Org buckets/datasets live on data_planes rows (auto-provisioned on
    # org create by the bingo-admin plugin), not env vars.
    disable_local_data_plane: bool = False

    # Internal Bingo-managed GCP (only required when disable_local_data_plane=True)
    internal_gcp_project: Optional[str] = None
    internal_gcs_bucket: Optional[str] = None  # legacy singleton — unused after Shape A; kept until env files migrate
    internal_bq_dataset: Optional[str] = None  # legacy singleton — unused after Shape A; kept until env files migrate
    internal_gcp_sa_json_path: Optional[str] = None
    internal_gcp_location: str = "US"   # GCS + BQ region for auto-provisioned per-Org buckets/datasets

    # GCS HMAC interop key for DuckDB-over-GCS serving (Phase 2). DuckDB's httpfs
    # GCS provider authenticates with an HMAC KEY_ID/SECRET, not the SA JSON.
    # Provision for the internal SA (projects.hmacKeys.create); empty → the
    # DuckDB-over-GCS serving path is unavailable and reads fall back to BQ.
    internal_gcs_hmac_key_id: Optional[str] = None
    internal_gcs_hmac_secret: Optional[str] = None

    # Signup flow — when on, every SSO sign-up creates a new Org (1 user = 1 Org).
    # Required for per-Org auto-provisioned internal-GCP planes (Shape A).
    per_user_org_signup: bool = False

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

    # Widget result cache (per-Org flag `widget_result_cache`)
    widget_cache_ttl_unfiltered: int = 3600   # exact until materialize bumps the generation
    widget_cache_ttl_filtered: int = 120      # filtered reads scan live Parquet; short staleness window
    widget_cache_ttl_source: int = 120        # live source-DB fallback: short window so repeat opens are fast without pinning stale data
    widget_cache_max_bytes: int = 2_000_000   # skip caching payloads larger than this

    # DuckDB memory guardrails (default memory_limit is ~80% of RAM per connection)
    duckdb_memory_limit: str = "1GB"
    duckdb_temp_directory: str = "/tmp/duckdb_spill"  # spill dir for large aggregations
    # DuckDB httpfs (GCS reads) network caps — a stalled read must abort under the
    # frontend's 60s fetch limit instead of hanging to a `<no response>` timeout.
    duckdb_http_timeout_ms: int = 30000   # per HTTP op to GCS
    duckdb_http_retries: int = 2

    # Source-DB connect cap for the widget query path (only test_connection set
    # one before, so an idle/cold source stalled with no client-side timeout).
    source_connect_timeout_s: int = 10
    # Per-query source-DB read cap. Sits under the 60s frontend fetch limit so a
    # slow/stalled source aborts before the client gives up (`<no response>`).
    source_read_timeout_s: int = 50

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
    orchestrator_lean_tools: bool = False  # ≤10 primary tools + manage meta-tool + @-mention scope
    dashboard_scoping_questions: bool = True  # ask audience/grain/time-range/metrics before building a dashboard
    template_backfill_on_startup: bool = True  # plugin-template framework: backfill existing connections at boot
    chat_export_enabled: bool = False  # "Data Export" (CSV/Excel) button on chat query results

    # LLM data-privacy floor (env LLM_METADATA_ONLY). True (default) forces
    # metadata-only on EVERY Org — real cell values never reach the LLM,
    # overriding each Org's metadata_only_llm flag. Set false to defer to the
    # per-Org flag (which itself defaults off = values shared).
    llm_metadata_only: bool = True

    # Maintenance mode — hides login UI behind a static page. Developers can bypass via
    # `?maint_bypass=KEY` URL param which the backend exchanges for an HttpOnly cookie.
    maintenance_mode: bool = False
    maintenance_bypass_key: str = ""           # empty → bypass disabled (404)
    maintenance_message: str = "Bingo is undergoing scheduled maintenance."
    maintenance_cookie_secure: bool = True     # set False over plain HTTP (local dev)

    # Connector picker visibility
    hidden_connector_types: str = ""  # comma-separated connector type_ids hidden from the picker

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

    @property
    def hidden_connector_type_set(self) -> set[str]:
        return {t.strip().lower() for t in self.hidden_connector_types.split(",") if t.strip()}

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore unknown env vars (e.g. JWT_SECRET_KEY from old .env files)
    )

# Singleton instance
settings = Settings()
