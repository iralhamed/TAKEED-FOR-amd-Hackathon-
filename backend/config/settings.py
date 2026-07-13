"""Central configuration for Ta'akkud.

All paths are resolved relative to the project root so the app behaves the same
regardless of the current working directory. Values can be overridden with
environment variables or a `.env` file at the project root.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/config/settings.py -> project root is three levels up.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_prefix="TAAKKUD_",
        extra="ignore",
    )

    # --- Storage locations (created on startup if missing) ---
    project_root: Path = PROJECT_ROOT
    laws_dir: Path = PROJECT_ROOT / "laws"
    uploads_dir: Path = PROJECT_ROOT / "uploads"
    reports_dir: Path = PROJECT_ROOT / "reports"
    database_dir: Path = PROJECT_ROOT / "database"

    # --- Database (SQLite for the MVP; schema stays Postgres-portable) ---
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'database' / 'taakkud.db'}"

    # --- Anthropic (used in phases 2 & 5 only) ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # --- Embeddings (phase 3) ---
    # Lightweight multilingual model (Arabic-capable), ONNX via fastembed.
    # ~0.22 GB on disk, ~650 MB RAM resident. 384-dim.
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384

    # --- Retrieval (phase 3) ---
    top_k: int = 5

    # --- Ingestion (phase 2) ---
    verbatim_match_threshold: int = 90  # rapidfuzz score 0-100
    ingest_chunk_pages: int = 4  # PDF pages per Claude digitization call

    def ensure_dirs(self) -> None:
        for d in (
            self.laws_dir,
            self.uploads_dir,
            self.reports_dir,
            self.database_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
