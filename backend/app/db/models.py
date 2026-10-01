from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Call(Base):
    __tablename__ = "calls"
    call_id: Mapped[str] = mapped_column(String, primary_key=True)
    product: Mapped[str] = mapped_column(String, default="business_loan")
    language: Mapped[str] = mapped_column(String, default="en")
    status: Mapped[str] = mapped_column(String, default="created")
    consent_obtained: Mapped[bool] = mapped_column(Boolean, default=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String, default=utc_now)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __mapper_args__ = {"version_id_col": revision}


class Lead(Base):
    __tablename__ = "leads"
    lead_id: Mapped[str] = mapped_column(String, primary_key=True)
    call_id: Mapped[str | None] = mapped_column(ForeignKey("calls.call_id"), nullable=True)
    name: Mapped[str] = mapped_column(String, default="Demo User")
    phone: Mapped[str] = mapped_column(String, default="[REDACTED]")
    requested_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    business_type: Mapped[str | None] = mapped_column(String, nullable=True)
    business_age_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_turnover: Mapped[float | None] = mapped_column(Float, nullable=True)
    existing_loan: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    qualification_status: Mapped[str] = mapped_column(String, default="incomplete")
    qualification_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    callback_requested: Mapped[bool] = mapped_column(Boolean, default=False)


class Callback(Base):
    __tablename__ = "callbacks"
    callback_id: Mapped[str] = mapped_column(String, primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.call_id"))
    requested_time: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="requested")


class Escalation(Base):
    __tablename__ = "escalations"
    escalation_id: Mapped[str] = mapped_column(String, primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.call_id"), index=True)
    reason: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="requested")
    created_at: Mapped[str] = mapped_column(String, default=utc_now)


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"
    segment_id: Mapped[str] = mapped_column(String, primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.call_id"), index=True)
    speaker: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(String)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int] = mapped_column(Integer)
    final: Mapped[bool] = mapped_column(Boolean, default=True)


class Signal(Base):
    __tablename__ = "signals"
    signal_id: Mapped[str] = mapped_column(String, primary_key=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.call_id"), index=True)
    type: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    evidence: Mapped[str] = mapped_column(String)
    speaker: Mapped[str] = mapped_column(String)
    detected_at_ms: Mapped[int] = mapped_column(Integer)
    priority: Mapped[str] = mapped_column(String)


class Nudge(Base):
    __tablename__ = "nudges"
    nudge_id: Mapped[str] = mapped_column(String, primary_key=True)
    signal_id: Mapped[str] = mapped_column(ForeignKey("signals.signal_id"))
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.call_id"), index=True)
    type: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(String)
    priority: Mapped[str] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    created_at_ms: Mapped[int] = mapped_column(Integer)
    expires_at_ms: Mapped[int] = mapped_column(Integer)
    suppression_key: Mapped[str] = mapped_column(String)


class LatencySample(Base):
    __tablename__ = "latency_samples"
    __table_args__ = (UniqueConstraint("call_id", "chunk_id"),)
    sample_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("calls.call_id"), index=True)
    chunk_id: Mapped[int] = mapped_column(Integer)
    audio_received_ms: Mapped[float] = mapped_column(Float)
    asr_done_ms: Mapped[float] = mapped_column(Float)
    signal_done_ms: Mapped[float] = mapped_column(Float)
    llm_done_ms: Mapped[float] = mapped_column(Float)
    delivered_ms: Mapped[float] = mapped_column(Float)
    asr_latency_ms: Mapped[float] = mapped_column(Float)
    signal_latency_ms: Mapped[float] = mapped_column(Float)
    llm_latency_ms: Mapped[float] = mapped_column(Float)
    delivery_latency_ms: Mapped[float] = mapped_column(Float)
    end_to_end_latency_ms: Mapped[float] = mapped_column(Float)
