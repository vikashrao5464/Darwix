import asyncio
import json

import pytest
from sqlalchemy import select

from app.db.models import Callback, Lead
from app.localization.language_state import LanguageState
from app.providers.mms_tts import MMSTTSProvider
from app.schemas.voice import ASRResult
from test_voice import wav


def start(client, scenario='ph_renewal', language='fil-en', **kwargs):
    response = client.post('/api/voice/calls', json={'scenario':scenario, 'response_language':language, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()


def turn(client, call, text, identifier='turn', **kwargs):
    response = client.post(f'/api/voice/calls/{call}/turn', json={'turn_id':identifier, 'text':text, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('scenario,language,consent,fallback', [
    ('ph_renewal','en','Yes','verified information'),
    ('ph_renewal','fil','Opo','beripikadong'),
    ('ph_renewal','fil-en','Opo','verified info'),
    ('id_installment','id-formal','Ya','terverifikasi'),
    ('id_installment','id-colloquial','Ya','belum bisa aku pastikan'),
    ('id_installment','id-en-mixed','Ya','belum verified'),
])
def test_all_registers_keep_same_language_fallback_and_grounded_reminder(indexed_client,scenario,language,consent,fallback):
    client = indexed_client
    call = start(client, scenario, language)['call_id']
    accepted = turn(client, call, consent, 'consent')
    assert accepted['language_state']['preferred_response_language'] == language
    assert accepted['grounded'] is True and accepted['citations']
    unknown = turn(client, call, 'xyz zzz', 'unknown')
    assert unknown['grounded'] is False and fallback in unknown['text']
    assert unknown['language_state']['preferred_response_language'] == language


def test_language_switch_and_sticky_acknowledgements(indexed_client):
    call = start(indexed_client, language='en')['call_id']
    turn(indexed_client, call, 'Yes', 'consent')
    reply = turn(indexed_client, call, 'Ano po ang premium?', 'taglish')
    assert reply['grounded'] and reply['language_state']['register'] == 'taglish'
    assert 'Ang premium po' in reply['text']
    assert turn(indexed_client, call, 'Opo', 'short')['language_state']['register'] == 'taglish'
    reply = turn(indexed_client, call, 'Ano ang hulog?', 'filipino')
    assert reply['language_state']['preferred_response_language'] == 'fil' and reply['grounded']
    reply = turn(indexed_client, call, 'What is coverage?', 'english')
    assert reply['language_state']['preferred_response_language'] == 'en' and reply['grounded']


def test_indonesian_register_switch_and_finance_loanwords(indexed_client):
    call = start(indexed_client, 'id_installment', 'id-formal')['call_id']
    turn(indexed_client, call, 'Ya', 'consent')
    colloquial = turn(indexed_client, call, 'Apa tenor itu, aku nggak ngerti?', 'colloquial')
    assert colloquial['grounded'] and colloquial['language_state']['register'] == 'colloquial'
    mixed = turn(indexed_client, call, 'Apa down payment itu?', 'mixed', response_language='id-en-mixed')
    assert mixed['grounded'] and 'DP' in mixed['text'] and 'down payment' in mixed['text']
    formal = turn(indexed_client, call, 'Mohon jelaskan pembiayaan', 'formal')
    assert formal['grounded'] and formal['language_state']['register'] == 'formal'


@pytest.mark.parametrize('scenario,language,question', [
    ('ph_renewal','fil-en','Ano po ang rider?'),
    ('ph_renewal','fil','Ano ang saklaw?'),
    ('ph_renewal','en','What is a beneficiary?'),
    ('id_installment','id-formal','Apa denda itu?'),
    ('id_installment','id-formal','Apakah cicilan itu?'),
    ('id_installment','id-colloquial','Apa DP itu?'),
    ('id_installment','id-en-mixed','Apa jatuh tempo atau due date?'),
])
def test_localized_faq_has_matching_source_and_no_cross_product_leak(indexed_client,scenario,language,question):
    call = start(indexed_client, scenario, language)['call_id']
    turn(indexed_client, call, 'Yes' if scenario == 'ph_renewal' else 'Ya', 'consent')
    reply = turn(indexed_client, call, question, 'faq', response_language=language)
    assert reply['grounded'] and reply['tools_called'] == ['search_knowledge']
    prefix = 'ph_reminder' if scenario == 'ph_renewal' else 'id_reminder'
    assert all(prefix in c['source'] and c['version']=='1.0' for c in reply['citations'])


def test_retrieval_miss_or_timeout_keeps_register(indexed_client,monkeypatch):
    call = start(indexed_client, 'id_installment', 'id-colloquial')['call_id']
    turn(indexed_client, call, 'Ya', 'consent')
    async def timeout(request):
        raise TimeoutError('provider unavailable')
    monkeypatch.setattr(indexed_client.app.state.voice_tools, 'search_knowledge', timeout)
    reply = turn(indexed_client, call, 'Apa tenor itu?', 'miss')
    assert not reply['grounded'] and 'belum bisa aku pastikan' in reply['text']
    assert reply['citations'] == []


def test_decline_prevents_retaining_customer_details_and_actions(client):
    call = start(client, language='fil')['call_id']
    turn(client, call, 'Email demo@example.test', 'preconsent')
    response = turn(client, call, 'Hindi po', 'decline')
    assert response['status'] == 'declined' and not response['recording_allowed']
    snapshot = client.get(f'/api/voice/calls/{call}').json()
    assert all(s['speaker']=='agent' for s in snapshot['transcript'])
    assert 'demo@example.test' not in json.dumps(snapshot)
    assert client.post(f'/api/voice/calls/{call}/turn', json={'turn_id':'later','text':'Opo'}).status_code == 409


def test_callback_time_confirmation_and_idempotency_use_shared_tool(indexed_client):
    call = start(indexed_client, 'id_installment', 'id-colloquial')['call_id']
    turn(indexed_client, call, 'Ya', 'consent')
    turn(indexed_client, call, 'Tolong telpon lagi', 'callback')
    candidate = turn(indexed_client, call, 'Besok jam tiga', 'time', require_confirmation=True)
    assert candidate['callback_id'] is None and 'Konfirmasi dulu' in candidate['text']
    result = turn(indexed_client, call, 'Ya', 'confirm')
    assert result['callback_id'] and result['tools_called'] == ['schedule_callback']
    assert turn(indexed_client, call, 'Ya', 'confirm') == result
    assert indexed_client.post(f'/api/voice/calls/{call}/turn',json={'turn_id':'confirm','text':'Tidak'}).status_code == 409
    with indexed_client.app.state.sessions() as session:
        callbacks = session.scalars(select(Callback).where(Callback.call_id==call)).all()
        assert len(callbacks)==1 and callbacks[0].requested_time=='Besok jam tiga'


def test_paid_statement_requires_confirmation_and_is_never_verified(indexed_client):
    call = start(indexed_client, 'id_installment', 'id-formal')['call_id']
    turn(indexed_client, call, 'Ya', 'consent')
    tentative = turn(indexed_client, call, 'Saya sudah membayar', 'paid')
    assert tentative['status']=='active' and 'Mohon konfirmasi' in tentative['text']
    confirmed = turn(indexed_client, call, 'Ya', 'confirm')
    assert confirmed['status']=='completed' and confirmed['reminder_status']=='customer_reports_paid'
    assert 'belum diverifikasi' in confirmed['text']
    with indexed_client.app.state.sessions() as session:
        assert session.scalars(select(Lead).where(Lead.call_id==call)).first() is None


def test_localized_escalation_before_consent_is_mock_and_redacted(client):
    call = start(client, 'id_installment', 'id-colloquial')['call_id']
    reply = turn(client, call, 'Aku mau petugas, email demo@example.test', 'human')
    assert reply['status']=='escalated' and reply['escalation_id']
    assert 'Belum ada yang dihubungi' in reply['text']
    snapshot = client.get(f'/api/voice/calls/{call}').json()
    assert all(s['speaker']=='agent' for s in snapshot['transcript'])


def test_unsupported_benefit_or_fee_waiver_cannot_be_invented(indexed_client):
    call = start(indexed_client)['call_id']
    turn(indexed_client, call, 'Opo', 'consent')
    reply = turn(indexed_client, call, 'Is cancer covered by my rider?', 'unsupported', response_language='fil-en')
    assert not reply['grounded'] and not reply['citations']
    assert 'verified info' in reply['text']


def test_wrong_market_language_and_business_tools_rejected(client):
    assert client.post('/api/voice/calls',json={'scenario':'ph_renewal','response_language':'id-formal'}).status_code==422
    call = start(client)['call_id']
    client.post('/api/voice/consent',json={'call_id':call,'consent':True})
    assert client.post('/api/voice/qualification',json={'call_id':call,'field':'requested_amount','value':100}).status_code==409
    assert client.post('/api/voice/eligibility',json={'call_id':call}).status_code==409
    assert client.post('/api/leads',json={'call_id':call}).status_code==409
    assert client.post('/api/voice/calls',json={'call_id':call}).status_code==409
    assert client.post(f'/api/voice/calls/{call}/turn',json={'turn_id':'bad','text':'test','response_language':'id-formal'}).status_code==422


def test_localized_uncertain_asr_preview_and_provider_timeout(client,monkeypatch):
    call = start(client, 'id_installment', 'id-colloquial')['call_id']
    async def unclear(audio,language):
        assert language=='id'
        return ASRResult(text='Email demo@example.test',confidence=.1)
    monkeypatch.setattr(client.app.state.localized_asr,'transcribe',unclear)
    result = client.post(f'/api/voice/calls/{call}/audio-turn?turn_id=unclear',content=wav()).json()
    assert result['review_required'] and '[EMAIL_REDACTED]' in result['review_text']
    assert 'datanya belum berubah' in result['message']
    assert client.get(f'/api/voice/calls/{call}').json()['status']=='awaiting_consent'
    async def timeout(audio,language): raise TimeoutError('private provider error')
    monkeypatch.setattr(client.app.state.localized_asr,'transcribe',timeout)
    result = client.post(f'/api/voice/calls/{call}/audio-turn?turn_id=timeout',content=wav()).json()
    assert result['reason']=='asr_unavailable' and 'datanya belum berubah' in result['message']


def test_localized_tts_failure_keeps_language(client,monkeypatch):
    call = start(client, 'id_installment', 'id-colloquial')['call_id']
    async def failure(text,language): raise TimeoutError()
    monkeypatch.setattr(client.app.state.localized_tts,'synthesize',failure)
    response = client.get(f'/api/voice/calls/{call}/speech/greeting')
    assert response.status_code==503 and 'Baca jawaban' in response.json()['detail']


def test_high_score_uninterpretable_fragment_keeps_taglish_fallback(indexed_client,monkeypatch):
    call = start(indexed_client,language='fil-en')['call_id']
    turn(indexed_client,call,'Opo','consent')
    async def recognize(audio,language):
        return ASRResult(text='To po ang pinyo',confidence=.8)
    monkeypatch.setattr(indexed_client.app.state.localized_asr,'transcribe',recognize)
    result = indexed_client.post(f'/api/voice/calls/{call}/audio-turn?turn_id=fragment',content=wav()).json()
    assert result['accepted'] and result['reply']['grounded'] is False
    assert result['reply']['language_state']['preferred_response_language']=='fil-en'
    assert 'verified info' in result['reply']['text']


@pytest.mark.parametrize('language,configured',[('fil','tl'),('fil-en',None),('en','en')])
def test_ph_speech_uses_selected_multilingual_language(client,monkeypatch,language,configured):
    call = start(client,language=language)['call_id']
    async def recognize(audio,language):
        assert language==configured
        return ASRResult(text='xyz',confidence=.1)
    monkeypatch.setattr(client.app.state.localized_asr,'transcribe',recognize)
    result = client.post(f'/api/voice/calls/{call}/audio-turn?turn_id=language',content=wav()).json()
    assert result['review_required'] and not result['accepted']


def test_missing_mms_model_falls_back_without_download(settings,tmp_path):
    settings.localization_tts_model_dir=tmp_path
    with pytest.raises(RuntimeError,match='setup_localization'):
        asyncio.run(MMSTTSProvider(settings,None).synthesize('Halo','id'))


@pytest.mark.parametrize('failure',['timeout','cancel'])
def test_mms_worker_timeout_and_cancel_are_reaped(settings,tmp_path,monkeypatch,failure):
    (tmp_path/'ind').mkdir()
    (tmp_path/'ind/config.json').write_text('{}')
    settings.localization_tts_model_dir=tmp_path
    settings.localization_tts_timeout_seconds=.01
    class Process:
        returncode=None
        killed=False
        reaped=False
        async def wait(self):
            if self.killed:
                self.returncode=-1
                self.reaped=True
                return -1
            await asyncio.sleep(10)
        def kill(self): self.killed=True
    process=Process()
    async def create(*args,**kwargs): return process
    monkeypatch.setattr(asyncio,'create_subprocess_exec',create)
    async def check():
        task=asyncio.create_task(MMSTTSProvider(settings,None).synthesize('Halo','id'))
        if failure=='cancel':
            await asyncio.sleep(.005)
            task.cancel()
        with pytest.raises(asyncio.CancelledError if failure=='cancel' else TimeoutError):
            await task
        assert process.killed and process.reaped
    asyncio.run(check())
