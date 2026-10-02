import logging
import uuid

from fastapi import HTTPException

from app.db.models import Call, Callback, Lead
from app.knowledge.pii import redact_pii
from app.schemas.voice import QualificationState
from app.voice.eligibility import evaluate_eligibility
from app.voice.escalation import request_escalation
from app.voice.qualification import CORE_FIELDS, update_field

logger = logging.getLogger("darwix.voice.tools")
TERMINAL = {"declined", "ended", "completed", "escalated"}


def log_tool(name):
    logger.info("voice_tool_called", extra={"tool_name": name})


class VoiceTools:
    def __init__(self, sessions, knowledge, settings):
        self.sessions, self.knowledge, self.settings = sessions, knowledge, settings

    def scrub(self, text):
        return redact_pii(text, self.settings.government_id_patterns).redacted_text

    def call(self, session, call_id, consent=False, active=False):
        call = session.get(Call, call_id)
        if call is None:
            raise HTTPException(404, "Call not found.")
        if consent and not call.consent_obtained:
            raise HTTPException(403, "Consent is required before collecting business details.")
        if active and call.status in TERMINAL:
            raise HTTPException(409, "The call has ended. Start a new call to collect details.")
        return call

    def qualification(self, call):
        return QualificationState.model_validate(call.state.get("qualification", {}))

    def set_qualification(self, call, qualification):
        call.state = {**call.state, "qualification": qualification.model_dump()}

    async def search_knowledge(self, request):
        log_tool("search_knowledge")
        return await self.knowledge.answer(request)

    def consent(self, request):
        with self.sessions() as session:
            call = self.call(session, request.call_id, active=True)
            call.consent_obtained = request.consent
            call.status = "active" if request.consent else "declined"
            call.state = {**call.state, "consent": "granted" if request.consent else "declined", "consent_saved":request.consent}
            session.commit()
            return {"call_id":call.call_id, "consent_obtained":call.consent_obtained, "status":call.status}

    def update_qualification(self, request):
        log_tool("update_qualification")
        with self.sessions() as session:
            call = self.call(session, request.call_id, consent=True, active=True)
            if call.product != "business_loan":
                raise HTTPException(409, "Qualification tools apply only to business-loan calls.")
            state = self.qualification(call)
            try:
                value = self.scrub(request.value) if isinstance(request.value, str) else request.value
                update_field(state, request.field, value, request.source_turn_id, request.status, request.resolve_conflict)
            except ValueError:
                raise HTTPException(422, "Invalid field value or conflict resolution.") from None
            self.set_qualification(call, state)
            session.commit()
            return {"call_id":call.call_id, "field":request.field, "state":state.fields[request.field].model_dump(),
                    "missing_fields":[field for field in CORE_FIELDS if state.fields[field].status != "confirmed"], "revision":call.revision}

    async def eligibility(self, call_id):
        log_tool("evaluate_preliminary_eligibility")
        with self.sessions() as session:
            call = self.call(session, call_id, consent=True)
            if call.product != "business_loan":
                raise HTTPException(409, "Eligibility tools apply only to business-loan calls.")
            return await evaluate_eligibility(self.qualification(call), self.knowledge, self.settings)

    async def lead(self, session, call):
        if call.product != "business_loan":
            raise HTTPException(409, "Lead tools apply only to business-loan calls.")
        log_tool("create_lead")
        if not call.consent_obtained:
            raise HTTPException(403, "Consent is required before creating a mock lead.")
        identifier = "lead_" + uuid.uuid5(uuid.NAMESPACE_URL, call.call_id).hex
        existing = session.get(Lead, identifier)
        if existing is not None:
            return {"lead_id":existing.lead_id, "qualification_status":existing.qualification_status, "mock":True}
        state = self.qualification(call)
        result = await evaluate_eligibility(state, self.knowledge, self.settings)
        values = {field:state.fields[field].value for field in CORE_FIELDS if state.fields[field].status == "confirmed"}
        session.add(Lead(lead_id=identifier, call_id=call.call_id, **values,
            qualification_status=result.status, qualification_reasons=result.reasons,
            callback_requested=bool(call.state.get("callback_id")) or state.fields["callback_preference"].value is True))
        call.status = "completed"
        return {"lead_id":identifier, "qualification_status":result.status, "mock":True}

    async def create_lead(self, request):
        with self.sessions() as session:
            call = self.call(session, request.call_id, consent=True)
            if call.status in {"declined", "ended", "escalated"}:
                raise HTTPException(409, "The call has ended.")
            result = await self.lead(session, call)
            session.commit()
            return result

    def callback(self, session, call, requested_time, reason):
        log_tool("schedule_callback")
        if not call.consent_obtained:
            raise HTTPException(403, "Consent is required to record a mock callback request.")
        identifier = "cb_" + uuid.uuid5(uuid.NAMESPACE_URL, call.call_id).hex
        requested_time = self.scrub(requested_time).strip()
        if len(requested_time) < 3 or requested_time in {"[PHONE_REDACTED]", "[EMAIL_REDACTED]", "[ACCOUNT_REDACTED]"}:
            raise HTTPException(422, "Provide a callback time preference.")
        existing = session.get(Callback, identifier)
        if existing is not None and existing.requested_time != requested_time:
            raise HTTPException(409, "A different callback time is already recorded for this call.")
        if existing is None:
            session.add(Callback(callback_id=identifier, call_id=call.call_id, requested_time=requested_time, reason=self.scrub(reason)))
        call.state = {**call.state, "callback_id":identifier}
        return {"callback_id":identifier, "requested_time":requested_time, "status":"requested", "mock":True}

    def schedule_callback(self, request):
        with self.sessions() as session:
            call = self.call(session, request.call_id, consent=True)
            if call.status in {"declined", "ended"}:
                raise HTTPException(409, "The call has ended.")
            result = self.callback(session, call, request.requested_time, request.reason)
            session.commit()
            return result

    def escalate(self, session, call, reason):
        log_tool("request_human_escalation")
        # Before consent retain only the action category, never customer details.
        identifier = request_escalation(session, call, self.scrub(reason) if call.consent_obtained else "Human assistance requested before consent")
        call.state = {**call.state, "escalation_id":identifier}
        return {"escalation_id":identifier, "status":"requested", "mock":True}

    def request_human_escalation(self, request):
        with self.sessions() as session:
            call = self.call(session, request.call_id)
            result = self.escalate(session, call, request.reason)
            session.commit()
            return result
