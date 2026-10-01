import json
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    database_url: str = "sqlite:///data/state/darwix.db"
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_path: str = "data/state/qdrant"
    qdrant_collection: str = "darwix_knowledge"
    qdrant_api_key: SecretStr = SecretStr("")
    embedding_provider: Literal["hash", "openai"] = "hash"
    embedding_dimensions: int = Field(default=512, ge=64, le=3072)
    embedding_model: str = "text-embedding-3-small"
    llm_provider: Literal["extractive", "openai"] = "extractive"
    llm_model: str = "gpt-4.1-mini"
    openai_api_key: SecretStr = SecretStr("")
    openai_base_url: str = "https://api.openai.com/v1"
    provider_timeout_seconds: float = Field(default=10, gt=0, le=120)
    retrieval_min_score: float = Field(default=0.3, ge=0, le=1)
    near_duplicate_threshold: float = Field(default=0.88, ge=0, le=1)
    chunk_words: int = Field(default=400, ge=50, le=600)
    chunk_overlap_words: int = Field(default=60, ge=0)
    terminology_path: str = "data/fixtures/terminology.json"
    government_id_patterns: list[str] = [r"\b\d{3}-\d{2}-\d{4}\b", r"\b\d{4} \d{4} \d{4}\b"]
    manifest_path: Path = ROOT / "data/raw/manifest.json"
    raw_dir: Path = ROOT / "data/raw"
    normalized_dir: Path = ROOT / "data/normalized"
    qualification_rules_path: Path = ROOT / "data/fixtures/qualification_rules.json"
    asr_provider: Literal["whisper", "windows"] = "whisper"
    asr_language: str = "en-US"
    tts_provider: Literal["windows"] = "windows"
    tts_voice: str = "Microsoft David Desktop"
    voice_asr_min_confidence: float = Field(default=0.55, ge=0, le=1)
    voice_max_turns: int = Field(default=60, ge=5, le=200)
    voice_audio_max_seconds: int = Field(default=20, ge=2, le=60)
    recordings_dir: Path = ROOT / "data/audio/private"
    whisper_model_name: Literal["base.en", "small.en"] = "small.en"
    whisper_model_dir: Path = ROOT / "data/state/models/whisper-small.en"
    whisper_cpu_threads: int = Field(default=2, ge=1, le=8)
    asr_timeout_seconds: float = Field(default=30, gt=0, le=120)
    whisper_min_score: float = Field(default=0.37, ge=0, le=1)

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.chunk_overlap_words >= self.chunk_words:
            raise ValueError("Chunk overlap must be smaller than chunk size")
        if "openai" in (self.embedding_provider, self.llm_provider) and not self.openai_api_key.get_secret_value():
            raise ValueError("OPENAI_API_KEY is required for an OpenAI provider")
        return self

    def terminology(self) -> dict[str, str]:
        path = Path(self.terminology_path)
        if not path.is_absolute():
            path = ROOT / path
        return json.loads(path.read_text(encoding="utf-8"))
