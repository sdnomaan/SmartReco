from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr


load_dotenv()


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    app_name: str = "SmartReco"
    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development").strip() or "development")
    mesh_api_key: SecretStr = Field(default_factory=lambda: SecretStr(os.getenv("MESH_API_KEY", "")))
    mesh_model: str = Field(default_factory=lambda: os.getenv("MESH_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini")
    mesh_embedding_model: str = Field(
        default_factory=lambda: os.getenv("MESH_EMBEDDING_MODEL", "text-embedding-3-small").strip()
        or "text-embedding-3-small"
    )
    database_url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/smartreco.db").strip() or "sqlite:///./data/smartreco.db"
    )
    chroma_path: Path = Field(default_factory=lambda: Path(os.getenv("CHROMA_PATH", "./data/chroma")).expanduser())
    session_secret: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("SESSION_SECRET", "smartreco-dev-session-secret"))
    )

    @property
    def mesh_api_key_value(self) -> str:
        return self.mesh_api_key.get_secret_value()

    @property
    def session_secret_value(self) -> str:
        return self.session_secret.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()