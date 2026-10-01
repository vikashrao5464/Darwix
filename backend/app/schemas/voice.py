from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

FieldName = Literal["requested_amount", "business_type", "business_age_months", "annual_turnover", "existing_loan", "city", "callback_preference"]
FieldValue = StrictBool | StrictInt | StrictFloat | StrictStr
Identifier = str


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QualificationField(StrictModel):
    value: FieldValue | None = None
    status: Literal["missing", "tentative", "confirmed", "conflicting"] = "missing"
    source_turn_id: str | None = None
    candidates: list[FieldValue] = Field(default_factory=list)


class QualificationState(StrictModel):
    fields: dict[FieldName, QualificationField] = Field(default_factory=lambda: {
        key: QualificationField() for key in (
            "requested_amount", "business_type", "business_age_months", "annual_turnover", "existing_loan", "city", "callback_preference")
    })


class CallCreate(StrictModel):
    call_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,80}$")
    recording_consent: StrictBool = False


class CallReference(StrictModel):
    call_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")


class ConsentRequest(CallReference):
    consent: StrictBool


class QualificationUpdate(CallReference):
    field: FieldName
    value: FieldValue
    source_turn_id: str = Field(default="tool_turn", pattern=r"^[A-Za-z0-9_-]{1,80}$")
    status: Literal["tentative", "confirmed"] = "confirmed"
    resolve_conflict: StrictBool = False


class TurnRequest(StrictModel):
    turn_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    text: str = Field(min_length=1, max_length=2000)
    start_ms: int = Field(default=0, ge=0)
    end_ms: int = Field(default=0, ge=0)
    require_confirmation: StrictBool = False

    @model_validator(mode="after")
    def validate_turn(self):
        if not self.text.strip() or self.end_ms < self.start_ms:
            raise ValueError("A nonblank turn with ordered timestamps is required")
        return self


class CallbackRequest(CallReference):
    requested_time: str = Field(min_length=3, max_length=120)
    reason: str = Field(default="Business-loan assistance", min_length=1, max_length=500)


class EscalationRequest(CallReference):
    reason: str = Field(default="Customer requested human assistance", min_length=1, max_length=500)


class LeadRequest(CallReference):
    pass


class InterpretedTurn(StrictModel):
    intent: Literal["details", "faq", "escalation", "callback", "create_lead", "end", "unknown"]
    field: FieldName | None
    evidence: str | None
    uncertain: bool


class EligibilityRule(StrictModel):
    rule_id: str
    field: FieldName
    operator: Literal[">=", "<=", "in", "review_if_true"]
    value: StrictInt | list[str] | StrictBool
    source_record_id: str
    source_version: str
    source_checksum: str
    source_quote: str
    explanation: str


class EligibilityResult(StrictModel):
    status: Literal["incomplete", "needs_human_review", "preliminarily_qualified", "not_preliminarily_qualified", "unavailable"]
    reasons: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    rules: list[dict] = Field(default_factory=list)
    synthetic: bool = True


class ASRResult(StrictModel):
    text: str
    confidence: float = Field(ge=0, le=1)


class CallReply(StrictModel):
    call_id: str
    turn_id: str
    text: str
    status: str
    qualification: QualificationState
    next_field: str | None = None
    citations: list[dict] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    grounded: bool | None = None
    eligibility: EligibilityResult | None = None
    lead_id: str | None = None
    callback_id: str | None = None
    escalation_id: str | None = None
    recording_allowed: bool = False
    revision: int
