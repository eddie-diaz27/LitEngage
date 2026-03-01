"""Central configuration management via pydantic-settings."""

from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from .env file."""

    # Gemini API
    google_api_key: str = "your_gemini_api_key_here"
    gemini_model: str = "gemini-2.0-flash-exp"
    gemini_temperature: float = 0.7
    gemini_max_tokens: int = 1024

    # DeepTeam guardrails
    deepteam_model: str = "gemini-2.0-flash-exp"
    enable_prompt_injection_guard: bool = True
    enable_topical_guard: bool = True
    enable_toxicity_guard: bool = True
    enable_privacy_guard: bool = True
    enable_hallucination_guard: bool = True
    allowed_topics: str = (
        "books,reading,library,literature,authors,genres,"
        "recommendations,stories,writing"
    )
    guardrail_sample_rate: float = 1.0

    # Database
    database_url: str = "sqlite:///./data/library.db"
    db_echo: bool = False

    # ChromaDB
    chroma_persist_directory: str = "./data/chroma_books_db"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimensions: int = 384
    chroma_collection_name: str = "school_books"

    # Vector search
    vector_search_k: int = 10
    vector_search_fetch_k: int = 30
    vector_search_lambda: float = 0.7
    default_recommendations_count: int = 3
    min_rating_threshold: float = 3.5

    # FastAPI
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:8501,http://localhost:3000,http://127.0.0.1:8501"
    api_prefix: str = "/api"
    enable_api_docs: bool = True

    # Streamlit
    backend_api_url: str = "http://localhost:8000"

    # Security
    secret_key: str = "dev-secret-key-change-in-production"

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/app.log"
    log_format: str = "json"

    # Dataset
    raw_data_dir: str = "./data/raw"
    processed_data_dir: str = "./data/processed"
    max_books_to_load: int = 0

    # Feature flags
    enable_librarian_review: bool = False
    enable_collaborative_filtering: bool = False

    # Compliance
    coppa_compliance_mode: bool = True
    ferpa_compliance_mode: bool = True
    anonymize_student_data: bool = True
    data_retention_days: int = 365

    # Environment
    environment: str = "development"
    debug: bool = True

    # LangSmith
    langchain_tracing_v2: bool = False
    langchain_api_key: Optional[str] = None
    langchain_project: str = "library-engagement-agent"

    # Testing
    test_database_url: str = "sqlite:///./data/test_library.db"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def allowed_topics_list(self) -> List[str]:
        return [topic.strip() for topic in self.allowed_topics.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
