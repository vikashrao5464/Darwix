from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.knowledge import KnowledgeRecord


class RetrievedRecord(KnowledgeRecord):
    score: float


class RetrievalResult(BaseModel):
    query: str
    records: list[RetrievedRecord] = Field(default_factory=list)
    grounded: bool = False
    reason: str | None = None


class Citation(BaseModel):
    record_id: str
    source: str
    source_type: str
    page: int | None
    section: str | None
    version: str
    synthetic: bool


class AnswerResult(BaseModel):
    answer: str
    grounded: bool
    citations: list[Citation] = Field(default_factory=list)
    reason: str | None = None
    mode: Literal["extractive", "openai"]
