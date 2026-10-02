from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

SignalType = Literal['missed_opportunity', 'compliance_risk', 'rising_frustration', 'payment_difficulty', 'callback_need']

class Candidate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: SignalType
    confidence: float = Field(ge=0, le=1)
    evidence: str = Field(min_length=1, max_length=500)
    speaker: Literal['agent', 'customer', 'unknown']
    priority: Literal['high', 'medium', 'low']

class SignalSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    signals: list[Candidate] = Field(default_factory=list, max_length=5)

class ReplayRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fixture_id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,80}$')
    call_id: str | None = Field(default=None, pattern=r'^[A-Za-z0-9_-]{1,80}$')

class Transcript(BaseModel):
    model_config = ConfigDict(extra='forbid')
    chunk_id: int = Field(ge=0)
    speaker: Literal['agent', 'customer', 'unknown']
    speaker_source: str = 'unknown; diarization unavailable'
    text: str = Field(max_length=3000)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)
    final: bool = True
    confidence: float = Field(ge=0, le=1)
    usable: bool = False
    @model_validator(mode='after')
    def ordered(self):
        if self.end_ms < self.start_ms: raise ValueError('invalid_time_range')
        return self
