from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATAAGENT_", env_file=".env", extra="ignore")

    database_url: str = "mysql+pymysql://root:root@127.0.0.1:3306/dataagent_python?charset=utf8mb4"
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_lock_ttl_ms: int = Field(default=30000, ge=1000, le=300000)
    data_dir: Path = Path("data")
    model_timeout: float = Field(default=30, gt=0, le=180)
    embedding_dimension: int = Field(default=0, ge=0)
    vector_backend: Literal["local", "elasticsearch", "milvus"] = "local"
    vector_url: str = ""
    vector_namespace: str = Field(default="dataagent", pattern=r"^[a-z][a-z0-9_]{0,47}$")
    vector_token: str = Field(default="", repr=False)

    @model_validator(mode="after")
    def validate_vector_endpoint(self):
        if self.vector_backend != "local":
            endpoint = urlsplit(self.vector_url)
            if (
                endpoint.scheme not in {"http", "https"}
                or not endpoint.hostname
                or endpoint.username
                or endpoint.password
                or endpoint.query
                or endpoint.fragment
            ):
                raise ValueError("External vector URL must be HTTP(S) without credentials or query")
        return self

    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_avatar_bytes: int = Field(default=5 * 1024 * 1024, gt=0)
    max_document_chars: int = Field(default=1000000, gt=0)
    parser_timeout: float = Field(default=60, gt=0, le=180)
    tika_app_jar: Path | None = None
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
