import asyncio
import hashlib
import logging
import re
import uuid

from fastapi import HTTPException

from app.db.models import Call, TranscriptSegment
from app.localization import indonesia, philippines
from app.localization.language_state import LanguageState
from app.schemas.knowledge import SearchRequest
from app.schemas.voice import CallReply, QualificationState
from app.voice.tools import TERMINAL

logger = logging.getLogger('darwix.localization')


def copy_for(state, key):
    module = philippines if state.market == 'PH' else indonesia
    return module.COPY[state.preferred_response_language][key]


def consent_value(text):
    text = re.sub(r'[^a-z ]', '', text.casefold()).strip()
    if re.fullmatch(r'(yes|yes please|yes po|oo|opo|oo po|sige|sige po|ya|iya|boleh|baik|setuju|lanjut)', text):
        return True
    if re.fullmatch(r'(no|no thanks|hindi|hindi po|ayaw|tidak|nggak|gak|enggak)', text):
        return False
    return None


class ReminderService:
    """Only reminder/language decisions differ; tools and persistence are shared."""
    def __init__(self, conversation):
        self.conversation = conversation
        self.tools = conversation.tools
        self.settings = conversation.settings

    def start(self, request):
        state = LanguageState.create('PH' if request.scenario == 'ph_renewal' else 'ID', request.response_language)
        call_id = request.call_id or 'call_' + uuid.uuid4().hex
        with self.tools.sessions() as session:
            call = session.get(Call, call_id)
            if call:
                if call.state.get('scenario', 'business_loan') != request.scenario:
                    raise HTTPException(409, 'Call ID belongs to another scenario.')
                return CallReply.model_validate(call.state['last_reply'])
            call = Call(call_id=call_id, product='life_insurance' if state.market == 'PH' else 'consumer_finance',
                        language=state.preferred_response_language, status='awaiting_consent', state={
                            'scenario': request.scenario, 'language_state': state.model_dump(),
                            'recording_consent': request.recording_consent, 'qualification': QualificationState().model_dump(),
                            'responses': {}, 'reminder_status': 'awaiting_consent'})
            session.add(call)
            session.flush()
            reply = CallReply(call_id=call_id, turn_id='greeting', text=copy_for(state, 'greeting'), status=call.status,
                              qualification=QualificationState(), scenario=request.scenario, language_state=state.model_dump(),
                              reminder_status='awaiting_consent', revision=call.revision + 1)
            call.state = {**call.state, 'last_reply': reply.model_dump(), 'greeting': reply.model_dump()}
            session.add(TranscriptSegment(segment_id=call_id + ':0000:1_agent', call_id=call_id,
                        speaker='agent', text=reply.text, start_ms=0, end_ms=0))
            session.commit()
            return reply

    async def evidence(self, call, state, topic):
        try:
            result = await asyncio.wait_for(self.tools.search_knowledge(SearchRequest(query=topic,
                product=call.product, language=state.preferred_response_language)), self.settings.provider_timeout_seconds)
            if result.grounded and result.citations:
                # Shared KB service verifies exact quotes and citations first.
                prefix = 'Synthetic demo information: '
                if result.answer.startswith(prefix):
                    return copy_for(state, 'synthetic') + result.answer[len(prefix):], [c.model_dump() for c in result.citations]
        except Exception as exc:
            logger.warning('localized_evidence_unavailable', extra={'error_type': type(exc).__name__})
        return copy_for(state, 'fallback'), []

    async def turn(self, call_id, request):
        fingerprint = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        with self.tools.sessions() as session:
            call = self.tools.call(session, call_id)
            previous = call.state.get('responses', {}).get(request.turn_id)
            if previous:
                if previous['input_hash'] != fingerprint:
                    raise HTTPException(409, 'Turn ID is already used for a different input.')
                return CallReply.model_validate(previous['reply'])
            if call.status in TERMINAL:
                raise HTTPException(409, 'The call has ended. Start a new call.')
            if len(call.state.get('responses', {})) >= self.settings.voice_max_turns:
                raise HTTPException(409, 'Call turn limit reached.')
            text = self.tools.scrub(request.text)
            language = LanguageState.model_validate(call.state['language_state'])
            try:
                language.update(text, request.response_language)
            except ValueError:
                raise HTTPException(422, 'Requested language is unavailable for this market.') from None
            call.language = language.preferred_response_language
            call.state = {**call.state, 'language_state': language.model_dump()}
            lower = text.casefold()
            def has(pattern):
                return re.search(pattern, lower) is not None
            def save(message, tools=None, citations=None, grounded=None, **actions):
                return self.conversation.save_reply(session, call, request, message, self.tools.qualification(call), fingerprint,
                    tools=tools, citations=citations, grounded=grounded, scenario=call.state['scenario'],
                    language_state=language.model_dump(), reminder_status=call.state.get('reminder_status'), **actions)
            def say(key, **kwargs):
                return save(copy_for(language, key), **kwargs)
            if has(r'\bhuman\b|\brepresentative\b|\bagent\b|\bkinatawan\b|\bkausap.*tao\b|\bpetugas\b|\boperator\b'):
                result = self.tools.escalate(session, call, 'Customer requested reminder assistance')
                call.state = {**call.state, 'reminder_status': 'escalation_requested'}
                return say('escalation', tools=['request_human_escalation'], escalation_id=result['escalation_id'])
            if has(r'\b(stop|end call|withdraw consent|itigil|tama na|hentikan|berhenti)\b'):
                call.status = 'ended'
                call.consent_obtained = False
                return say('ended')
            if not call.consent_obtained:
                consent = consent_value(lower)
                if consent is None:
                    return say('consent')
                call.consent_obtained = consent
                call.status = 'active' if consent else 'declined'
                call.state = {**call.state, 'reminder_status': 'discussing' if consent else 'declined'}
                if not consent:
                    return say('declined')
                message, citations = await self.evidence(call, language, 'reminder')
                return save(message + ' ' + copy_for(language, 'question'), tools=['search_knowledge'], citations=citations, grounded=bool(citations))
            pending = call.state.get('pending_action')
            if pending == 'confirm_paid' and consent_value(lower) is not None:
                confirmed = consent_value(lower)
                call.state = {**call.state, 'pending_action': None, 'reminder_status': 'customer_reports_paid' if confirmed else 'discussing'}
                if confirmed:
                    call.status = 'completed'
                    return say('paid')
                return say('question')
            if pending == 'confirm_callback' and consent_value(lower) is not None:
                value = call.state.get('callback_candidate')
                call.state = {**call.state, 'pending_action': 'callback_time', 'callback_candidate': None}
                if consent_value(lower) is True:
                    result = self.tools.callback(session, call, value, 'Customer requested reminder callback')
                    call.state = {**call.state, 'pending_action': None, 'reminder_status': 'callback_requested'}
                    return say('callback_saved', tools=['schedule_callback'], callback_id=result['callback_id'])
                return say('callback')
            if has(r'\b(already paid|paid already|paid na|nakapagbayad|bayad na|sudah bayar|sudah membayar|udah bayar)\b'):
                call.state = {**call.state, 'pending_action': 'confirm_paid'}
                return say('confirm_paid')
            if has(r'\b(cannot pay|can.t pay|no money|mahirap|wala.*pera|hindi.*bayad|sulit.*bayar|susah.*bayar|belum.*uang|nggak.*uang|gak.*bayar|cash flow)\b'):
                return say('difficulty')
            if has(r'\b(callback|call back|call me|tawag|magpatawag|telepon|telpon|hubungi)\b') and pending != 'callback_time':
                call.state = {**call.state, 'pending_action': 'callback_time'}
                return say('callback')
            if pending == 'callback_time' and has(r'\b(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|bukas|ngayon|lunes|martes|miyerkules|huwebes|biyernes|sabado|linggo|besok|hari|senin|selasa|rabu|kamis|jumat|sabtu|minggu|jam|alas)\b|\b\d{1,2}[:.]\d{2}\b'):
                if len(text) > 120:
                    return say('callback')
                if request.require_confirmation:
                    call.state = {**call.state, 'pending_action': 'confirm_callback', 'callback_candidate': text}
                    return save(copy_for(language, 'confirm_time').format(value=text))
                result = self.tools.callback(session, call, text, 'Customer requested reminder callback')
                call.state = {**call.state, 'pending_action': None, 'reminder_status': 'callback_requested'}
                return say('callback_saved', tools=['schedule_callback'], callback_id=result['callback_id'])
            module = philippines if language.market == 'PH' else indonesia
            # Only definition/reminder questions are mapped to supported topics.
            # Specific benefits, waivers, promises and approvals remain unavailable.
            definition = has(r'\b(what|meaning|ano|ibig sabihin|apa|apakah|maksud|explain|jelaskan|magkano|kailan|berapa|kapan)\b')
            unsupported = has(r'\b(guarantee|guaranteed|cancer|covered|waive|hapus|gratis|cashback|approve|approved|discount|refund|pasti|free)\b')
            if definition and not unsupported:
                topic = next((key for key, pattern in module.TOPICS.items() if has(pattern)), None)
                if topic:
                    message, citations = await self.evidence(call, language, topic)
                    return save(message, tools=['search_knowledge'], citations=citations, grounded=bool(citations))
            return say('fallback', grounded=False)
