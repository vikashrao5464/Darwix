import asyncio
import hashlib
import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import Call, TranscriptSegment
from app.schemas.knowledge import SearchRequest
from app.schemas.voice import CallReply, QualificationState
from app.voice.conversation_rules import DECLINED, GREETING
from app.voice.eligibility import evaluate_eligibility
from app.voice.interpretation import field_value, interpret_local, yes_no
from app.voice.qualification import equal_values, next_field, question, update_field
from app.voice.tools import TERMINAL, log_tool

logger = logging.getLogger("darwix.voice.conversation")


class ConversationService:
    def __init__(self, tools, llm, settings):
        self.tools, self.llm, self.settings = tools, llm, settings
        from app.localization.reminders import ReminderService
        self.reminders = ReminderService(self)

    def start_call(self, request):
        if request.scenario != "business_loan":
            return self.reminders.start(request)
        call_id = request.call_id or "call_" + uuid.uuid4().hex
        with self.tools.sessions() as session:
            existing = session.get(Call, call_id)
            if existing is not None:
                if existing.state.get("scenario", "business_loan") != request.scenario:
                    raise HTTPException(409, "Call ID belongs to another scenario.")
                if "last_reply" not in existing.state:
                    raise HTTPException(409, "This ID belongs to a legacy call. Start a call with a new ID.")
                return CallReply.model_validate(existing.state["last_reply"])
            state = QualificationState()
            call = Call(call_id=call_id, status="awaiting_consent", state={"qualification":state.model_dump(),
                "recording_consent":request.recording_consent, "responses":{}, "pending_action":None})
            session.add(call)
            session.flush()
            reply = CallReply(call_id=call_id, turn_id="greeting", text=GREETING, status=call.status,
                              qualification=state, revision=call.revision + 1)
            call.state = {**call.state, "last_reply":reply.model_dump(), "greeting":reply.model_dump()}
            session.add(TranscriptSegment(segment_id=call_id + ":0000:1_agent", call_id=call_id, speaker="agent", text=GREETING, start_ms=0, end_ms=0))
            session.commit()
            return reply

    def snapshot(self, call_id):
        with self.tools.sessions() as session:
            call = self.tools.call(session, call_id)
            segments = session.scalars(select(TranscriptSegment).where(TranscriptSegment.call_id == call_id).order_by(TranscriptSegment.segment_id)).all()
            return {"call_id":call_id, "status":call.status, "consent_obtained":call.consent_obtained,
                "qualification":self.tools.qualification(call).model_dump(), "revision":call.revision,
                "last_reply":call.state["last_reply"], "transcript":[{"speaker":s.speaker, "text":s.text, "start_ms":s.start_ms, "end_ms":s.end_ms} for s in segments]}

    async def interpretation(self, text, pending):
        if self.settings.llm_provider == "extractive":
            return interpret_local(text, pending)
        try:
            interpreted = await asyncio.wait_for(self.llm.interpret_turn(text, pending), self.settings.provider_timeout_seconds)
            if interpreted.evidence and interpreted.evidence not in text:
                raise ValueError("invented_customer_evidence")
            if interpreted.intent == "details" and (not interpreted.field or not interpreted.evidence):
                raise ValueError("missing_customer_evidence")
            return interpreted
        except Exception as exc:
            logger.warning("turn_interpretation_unavailable", extra={"error_type":type(exc).__name__})
            return None

    def save_reply(self, session, call, request, text, state, input_hash, tools=None, citations=None, grounded=None, eligibility=None, **actions):
        reply = CallReply(call_id=call.call_id, turn_id=request.turn_id, text=text, status=call.status,
            qualification=state, next_field=next_field(state), citations=citations or [], tools_called=tools or [],
            grounded=grounded, eligibility=eligibility, recording_allowed=call.consent_obtained and call.state.get("recording_consent", False),
            revision=call.revision + 1, **actions)
        responses = {**call.state.get("responses", {}), request.turn_id:{"input_hash":input_hash, "reply":reply.model_dump()}}
        call.state = {**call.state, "qualification":state.model_dump(), "responses":responses, "last_reply":reply.model_dump()}
        position = len(responses)
        if call.consent_obtained:
            customer_text = "Consent granted." if not call.state.get("consent_saved") else self.tools.scrub(request.text)
            call.state = {**call.state, "consent_saved":True}
            session.add(TranscriptSegment(segment_id=f"{call.call_id}:{position:04d}:0_customer", call_id=call.call_id,
                speaker="customer", text=customer_text, start_ms=request.start_ms, end_ms=request.end_ms))
        session.add(TranscriptSegment(segment_id=f"{call.call_id}:{position:04d}:1_agent", call_id=call.call_id,
            speaker="agent", text=text, start_ms=request.end_ms, end_ms=request.end_ms))
        session.commit()
        return reply

    async def turn(self, call_id, request):
        with self.tools.sessions() as session:
            call = self.tools.call(session, call_id)
            localized = call.state.get("scenario", "business_loan") != "business_loan"
        if localized:
            return await self.reminders.turn(call_id, request)
        if request.response_language not in {None, "en"}:
            raise HTTPException(422, "The business-loan scenario supports English.")
        fingerprint = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        with self.tools.sessions() as session:
            call = self.tools.call(session, call_id)
            previous = call.state.get("responses", {}).get(request.turn_id)
            if previous:
                if previous["input_hash"] != fingerprint:
                    raise HTTPException(409, "Turn ID is already used for a different input.")
                return CallReply.model_validate(previous["reply"])
            if call.status in TERMINAL:
                raise HTTPException(409, "The call has ended. Start a new call.")
            if len(call.state.get("responses", {})) >= self.settings.voice_max_turns:
                raise HTTPException(409, "Call turn limit reached. End this call and start a new one.")
            state = self.tools.qualification(call)
            text = self.tools.scrub(request.text)
            # Escalation is available even before qualification consent.
            local = interpret_local(text, next_field(state))
            if local.intent == "escalation":
                result = self.tools.escalate(session, call, "Customer requested human assistance")
                return self.save_reply(session, call, request, "I recorded a mock human-assistance request. No representative has been contacted by this demo.", state, fingerprint,
                    tools=["request_human_escalation"], escalation_id=result["escalation_id"])
            if not call.consent_obtained:
                consent = yes_no(text)
                if consent is None:
                    return self.save_reply(session, call, request, "May I collect business details for this synthetic preliminary qualification demo? Please say yes or no.", state, fingerprint)
                call.consent_obtained = consent
                call.status = "active" if consent else "declined"
                _, prompt = question(state)
                return self.save_reply(session, call, request, prompt if consent else DECLINED, state, fingerprint)
            if local.intent == "end":
                if "withdraw consent" in text.casefold():
                    call.consent_obtained = False
                call.status = "ended"
                return self.save_reply(session, call, request, "I have stopped the call and will collect no further details.", state, fingerprint)
            pending_action = call.state.get("pending_action")
            if pending_action == "callback_time" and local.intent not in {"faq", "escalation"}:
                result = self.tools.callback(session, call, text, "Customer requested a callback")
                call.state = {**call.state, "pending_action":None if next_field(state) else "create_lead"}
                _, prompt = question(state)
                return self.save_reply(session, call, request, "The mock callback time preference is recorded. A coordinator would need to confirm the appointment. " + (prompt or "Would you like a mock lead created?"), state, fingerprint,
                    tools=["schedule_callback"], callback_id=result["callback_id"])
            if (pending_action == "create_lead" and yes_no(text) is True) or local.intent == "create_lead":
                result = await self.tools.lead(session, call)
                return self.save_reply(session, call, request, "I created a mock lead with the preliminary assessment. This demo has not submitted a loan application or made an approval decision.", state, fingerprint,
                    tools=["create_lead"], lead_id=result["lead_id"])
            if pending_action == "create_lead" and yes_no(text) is False:
                call.status = "ended"
                return self.save_reply(session, call, request, "Understood. I will finish here without creating a lead.", state, fingerprint)
            interpreted = await self.interpretation(text, next_field(state))
            if interpreted is None:
                return self.save_reply(session, call, request, "I could not interpret that reliably. Please repeat one business detail, or request human assistance.", state, fingerprint)
            if interpreted.intent == "faq":
                answer = await self.tools.search_knowledge(SearchRequest(query=text, product="business_loan", language="en"))
                return self.save_reply(session, call, request, answer.answer, state, fingerprint,
                    tools=["search_knowledge"], citations=[c.model_dump() for c in answer.citations], grounded=answer.grounded)
            if interpreted.intent == "escalation":
                result = self.tools.escalate(session, call, "Customer requested human assistance")
                return self.save_reply(session, call, request, "I recorded a mock human-assistance request. No representative has been contacted by this demo.", state, fingerprint,
                    tools=["request_human_escalation"], escalation_id=result["escalation_id"])
            if interpreted.intent == "callback":
                call.state = {**call.state, "pending_action":"callback_time"}
                return self.save_reply(session, call, request, "What day and time would you prefer for a mock callback?", state, fingerprint)
            if interpreted.intent == "end":
                call.status = "ended"
                return self.save_reply(session, call, request, "I have stopped the call and will collect no further details.", state, fingerprint)
            if interpreted.intent == "create_lead":
                result = await self.tools.lead(session, call)
                return self.save_reply(session, call, request, "I created a mock lead with the preliminary assessment. This demo has not submitted a loan application or made an approval decision.", state, fingerprint,
                    tools=["create_lead"], lead_id=result["lead_id"])
            field = interpreted.field
            value = field_value(field, interpreted.evidence or text) if field else None
            current = state.fields.get(field) if field else None
            if current and current.status == "tentative" and yes_no(text) is True:
                value = current.value
            resolving = bool(current and current.status == "conflicting" and field == next_field(state) and
                             value is not None and any(equal_values(value, candidate) for candidate in current.candidates))
            if field and value is not None:
                try:
                    confirmation_pending = request.require_confirmation and current.status != "tentative" and not resolving
                    update_field(state, field, value, request.turn_id, "tentative" if interpreted.uncertain or confirmation_pending else "confirmed", resolving)
                except ValueError:
                    value = None
            if value is None:
                _, prompt = question(state)
                return self.save_reply(session, call, request, "I need an explicit value to avoid guessing. " + (prompt or "Please request a callback, a mock lead, or human assistance."), state, fingerprint)
            log_tool("update_qualification")
            self.tools.set_qualification(call, state)
            if field == "callback_preference" and value is True and state.fields[field].status == "confirmed":
                call.state = {**call.state, "pending_action":"callback_time"}
                return self.save_reply(session, call, request, "What day and time would you prefer for the mock callback?", state, fingerprint, tools=["update_qualification"])
            _, prompt = question(state)
            if prompt:
                return self.save_reply(session, call, request, prompt, state, fingerprint, tools=["update_qualification"])
            log_tool("evaluate_preliminary_eligibility")
            eligibility = await evaluate_eligibility(state, self.tools.knowledge, self.settings)
            outcomes = {"preliminarily_qualified":"Your confirmed details meet the synthetic preliminary criteria; this is not final approval.",
                "not_preliminarily_qualified":"Your confirmed details do not meet all synthetic preliminary criteria.",
                "needs_human_review":"Your confirmed details need human review before a preliminary outcome can be finalized.",
                "unavailable":"Verified qualification rules are unavailable, so I cannot assess eligibility.", "incomplete":"More confirmed details are needed."}
            call.state = {**call.state, "pending_action":"create_lead"}
            return self.save_reply(session, call, request, outcomes[eligibility.status] + " Would you like a mock lead created?", state, fingerprint,
                tools=["update_qualification", "evaluate_preliminary_eligibility"], eligibility=eligibility,
                citations=list({r["citation"]["record_id"]:r["citation"] for r in eligibility.rules}.values()))

    def end_call(self, call_id):
        with self.tools.sessions() as session:
            call = self.tools.call(session, call_id)
            if call.status not in TERMINAL:
                call.status = "ended"
                session.commit()
            return {"call_id":call_id, "status":call.status}
