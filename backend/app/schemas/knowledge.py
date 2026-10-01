from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    path: str
    source_type: Literal["pdf", "html", "markdown", "text", "json", "csv"]
    product: str
    version: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    language: str = "en"
    category: Literal["product", "policy", "qualification", "faq", "objection", "support"] = "policy"
    synthetic: bool = True


class ExtractedUnit(BaseModel):
    document_id: str
    text: str
    source: str
    page: int | None = None
    section: str | None = None
    metadata: dict = Field(default_factory=dict)


class KnowledgeRecord(BaseModel):
    record_id: str
    document_id: str
    title: str
    content: str
    category: str
    product: str
    source: str
    source_type: str
    source_page: int | None = None
    source_section: str | None = None
    version: str
    contains_pii: bool
    language: str
    checksum: str
    synthetic: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paths: list[str] = Field(min_length=1, max_length=100)
    version: str = Field(default="1.0", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    product: str = Field(default="business_loan", min_length=1, max_length=100)
    language: str = Field(default="en", min_length=1, max_length=30)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Query cannot be blank")
        return value


class SourceStatus(BaseModel):
    document_id: str
    source: str
    status: Literal["success", "failed"]
    unit_count: int = 0
    error: str | None = None


class IngestionReport(BaseModel):
    status: Literal["success", "partial", "failed"] = "success"
    sources: list[SourceStatus] = Field(default_factory=list)
    dedupe_decisions: list[dict] = Field(default_factory=list)
    indexed_records: int = 0
    collection_records: int = 0
    collection: str = ""
    embedding_provider: str = ""
    duration_ms: float = 0
    error: str | None = None
