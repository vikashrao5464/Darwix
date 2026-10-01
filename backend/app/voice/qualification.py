import math

from app.schemas.voice import QualificationField, QualificationState

CORE_FIELDS = ("requested_amount", "business_type", "business_age_months", "annual_turnover", "existing_loan", "city")
FIELD_ORDER = (*CORE_FIELDS, "callback_preference")
QUESTIONS = {
    "requested_amount": "What loan amount would you like to request, in INR?",
    "business_type": "What type of business do you operate?",
    "business_age_months": "How many months or years has your business been operating?",
    "annual_turnover": "What is your annual business turnover, in INR?",
    "existing_loan": "Does your business currently have an existing loan?",
    "city": "In which city is your business located?",
    "callback_preference": "Would you like a mock callback request recorded?",
}


def validate_value(field, value):
    if field in {"requested_amount", "annual_turnover"}:
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 1e12:
            raise ValueError("A positive finite amount is required")
    elif field == "business_age_months":
        if type(value) is not int or not 0 <= value <= 1200:
            raise ValueError("Business age must be whole months between 0 and 1200")
    elif field in {"existing_loan", "callback_preference"}:
        if type(value) is not bool:
            raise ValueError("An explicit boolean is required")
    elif field in {"business_type", "city"}:
        if not isinstance(value, str) or not value.strip() or len(value) > 100:
            raise ValueError("A nonblank value of at most 100 characters is required")
        value = value.strip()
        if "REDACTED]" in value:
            raise ValueError("Personal identifiers cannot be used as business details")
    else:
        raise ValueError("Unknown qualification field")
    return value


def equal_values(left, right):
    if isinstance(left, str) and isinstance(right, str):
        return left.casefold() == right.casefold()
    return type(left) is type(right) and left == right or type(left) in (int, float) and type(right) in (int, float) and left == right


def update_field(state: QualificationState, field, value, turn_id, status="confirmed", resolve_conflict=False):
    value = validate_value(field, value)
    previous = state.fields[field]
    if resolve_conflict:
        if previous.status != "conflicting" or status != "confirmed":
            raise ValueError("Only explicit confirmation may resolve a conflict")
        state.fields[field] = QualificationField(value=value, status="confirmed", source_turn_id=turn_id)
    elif previous.status == "missing":
        state.fields[field] = QualificationField(value=value, status=status, source_turn_id=turn_id)
    elif equal_values(previous.value, value) and previous.status != "conflicting":
        state.fields[field] = QualificationField(value=value, status="confirmed" if status == "confirmed" else previous.status,
                                                  source_turn_id=turn_id)
    else:
        candidates = list(previous.candidates or [previous.value])
        if not any(equal_values(candidate, value) for candidate in candidates):
            candidates.append(value)
        state.fields[field] = QualificationField(value=previous.value, status="conflicting",
                                                  source_turn_id=previous.source_turn_id, candidates=candidates)
    return state


def next_field(state):
    for status in ("conflicting", "tentative", "missing"):
        for field in FIELD_ORDER:
            if state.fields[field].status == status:
                return field
    return None


def question(state):
    field = next_field(state)
    if field is None:
        return None, None
    current = state.fields[field]
    label = field.replace("_", " ")
    if current.status == "conflicting":
        return field, f"I have conflicting values for {label}: {', '.join(str(v) for v in current.candidates)}. Please confirm the correct value."
    if current.status == "tentative":
        return field, f"You mentioned {current.value} for {label}. Please confirm that value or provide a correction."
    return field, QUESTIONS[field]
