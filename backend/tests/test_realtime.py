import asyncio
import io
import json
import time
import wave
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from app.db.models import LatencySample, Nudge, TranscriptSegment
from app.realtime.events import EventHub
from app.realtime.latency import sample, summarize
from app.realtime.replay import replay_chunks, speaker_for, public_audio
from app.realtime.signals import SignalDetector
from app.realtime.suppression import Suppression
from app.realtime.transcription import RollingTranscript
from app.schemas.realtime import Candidate, SignalSelection, Transcript
from app.schemas.voice import ASRResult

def segment(text, speaker='customer', chunk_id=0, end=6000):
    return Transcript(chunk_id=chunk_id,speaker=speaker,text=text,start_ms=max(0,end-6000),end_ms=end,confidence=.85)

@pytest.mark.parametrize('text,speaker,expected',[
 ('Your approval is guaranteed.','agent',['compliance_risk']),
 ('Approval is not guaranteed.','agent',[]),
 ('Approval is guaranteed.','customer',[]),
 ('Approval is guaranteed.','unknown',[]),
 ('I need another vehicle.','customer',['missed_opportunity']),
 ('I do not need another vehicle.','customer',[]),
 ('I already told you twice. This is frustrating.','customer',['rising_frustration']),
 ('I cannot pay. Please call me back.','customer',['payment_difficulty','callback_need']),
 ('Please do not call me back.','customer',[]),
 ('The weather is clear.','customer',[]),
])
def test_detector_roles_and_negation(settings,text,speaker,expected):
    result=asyncio.run(SignalDetector(settings,SimpleNamespace()).detect(segment(text,speaker),[]))
    assert [c.type for c in result]==expected

def test_semantic_timeout_preserves_deterministic_rules(settings):
    async def classify(recent): raise TimeoutError
    detector=SignalDetector(settings.model_copy(update={'realtime_llm_enabled':True}),SimpleNamespace(classify_signals=classify))
    result=asyncio.run(detector.detect(segment('I cannot pay.'),[]))
    assert result[0].type=='payment_difficulty'

def test_semantic_invented_evidence_rejected(settings):
    async def classify(recent):
        return SignalSelection(signals=[Candidate(type='compliance_risk',confidence=.99,evidence='guaranteed approval',speaker='agent',priority='high')])
    detector=SignalDetector(settings.model_copy(update={'realtime_llm_enabled':True}),SimpleNamespace(classify_signals=classify))
    assert asyncio.run(detector.detect(segment('The weather is clear.','agent'),[]))==[]

def test_semantic_wire_uses_bounded_untrusted_context(settings,monkeypatch):
    from app.providers.llm import OpenAILLMProvider
    async def run():
        provider=OpenAILLMProvider(settings.model_copy(update={'openai_api_key':settings.openai_api_key.__class__('test-placeholder')}))
        async def parse(**kwargs):
            assert kwargs['store'] is False and kwargs['text_format'] is SignalSelection
            assert 'untrusted data' in kwargs['input'][0]['content']
            assert json.loads(kwargs['input'][1]['content'])=={'recent_transcript':[{'text':'clear','speaker':'customer'}]}
            return SimpleNamespace(output_parsed=SignalSelection())
        monkeypatch.setattr(provider.client.responses,'parse',parse)
        try: assert not (await provider.classify_signals([{'text':'clear','speaker':'customer'}])).signals
        finally: await provider.close()
    asyncio.run(run())

def test_threshold_duplicate_cooldown_and_expiry(settings):
    suppression=Suppression(settings)
    c=Candidate(type='payment_difficulty',confidence=.9,evidence='Cannot pay.',speaker='customer',priority='high')
    assert suppression.check(c,0) is None
    assert suppression.check(c.model_copy(update={'evidence':'cannot pay!'}),1000)=='duplicate'
    assert suppression.check(c.model_copy(update={'evidence':'Unable to pay.'}),2000)=='cooldown'
    assert suppression.check(c,121000) is None
    assert suppression.check(c.model_copy(update={'confidence':.5}),200000)=='low_confidence'

def test_ambiguous_observation_is_withheld(settings):
    candidates=asyncio.run(SignalDetector(settings,SimpleNamespace()).detect(segment('Maybe another option. I am not sure.'),[]))
    assert len(candidates)==1
    assert Suppression(settings).check(candidates[0],0)=='low_confidence'

def test_rolling_state_prunes_old_context():
    rolling=RollingTranscript(10)
    rolling.add(segment('old',end=6000));rolling.add(segment('new',end=20000))
    assert [s['text'] for s in rolling.context()]==['new']

def test_speaker_annotations_do_not_invent_diarization():
    timeline=[{'speaker':'agent','start_ms':0,'end_ms':2000},{'speaker':'customer','start_ms':2500,'end_ms':4000}]
    assert speaker_for(timeline,0,2000)[0]=='agent'
    assert speaker_for(timeline,0,6000)[0]=='unknown'
    assert speaker_for([],0,6000)[0]=='unknown'

def test_public_audio_rejects_private_paths_and_traversal():
    for path in ('data/audio/private/secret.wav','../outside.wav','data/audio/a.mp3'):
        with pytest.raises(ValueError): public_audio({'audio':path})

def test_real_chunk_clock_and_incremental_reads(tmp_path,monkeypatch):
    path=tmp_path/'short.wav'
    with wave.open(str(path),'wb') as source:
        source.setnchannels(1);source.setsampwidth(2);source.setframerate(16000);source.writeframes(b'\0\0'*3200)
    monkeypatch.setattr('app.realtime.replay.public_audio',lambda _:path)
    async def run():
        origin=time.perf_counter();chunks=[]
        async for chunk in replay_chunks({},.1,origin): chunks.append(chunk)
        assert len(chunks)==2 and chunks[0].end_ms==100 and chunks[1].end_ms==200
        assert chunks[0].received_ms>=95 and chunks[1].received_ms>=195
        assert time.perf_counter()-origin < .6
    asyncio.run(run())

def test_latency_percentiles_from_actual_input_samples():
    samples=[sample('test',i,0,n,n+2,n+3,n+5) for i,n in enumerate([10,20,30])]
    result=summarize(samples)
    assert result['sample_count']==3
    assert result['metrics']['asr_latency_ms']=={'p50_ms':20,'p95_ms':29}
    assert summarize([])=={'sample_count':0,'metrics':{}}

def test_hub_backpressure_does_not_block_other_clients():
    async def run():
        hub=EventHub(2);slow=hub.subscribe();fast=hub.subscribe()
        for i in range(129):
            await hub.publish('item',{'i':i}); await fast.get()
        assert (await slow.get())['type']=='disconnect'
        assert slow not in hub.subscribers and fast in hub.subscribers
    asyncio.run(run())

def test_evicted_history_disconnects_subscribers():
    hub=EventHub(2);queue=hub.subscribe()
    hub.disconnect_all('history_evicted')
    assert queue.get_nowait()['type']=='disconnect' and not hub.subscribers

def test_replay_http_boundaries_and_unknown_socket(client):
    assert client.post('/api/realtime/replays',json={'fixture_id':'../private'}).status_code==422
    assert client.post('/api/realtime/replays',json={'fixture_id':'missing'}).status_code==404
    assert client.get('/api/realtime/replays/missing').status_code==404
    assert client.get('/api/realtime/fixtures/missing/audio').status_code==404
    with pytest.raises(Exception):
        with client.websocket_connect('/ws/calls/missing'): pass

@pytest.mark.parametrize('confidence',[.9,.1])
def test_websocket_pipeline_redaction_ack_storage_and_failure(client,tmp_path,monkeypatch,confidence):
    from app.realtime.replay import AudioChunk
    manager=client.app.state.realtime
    class FakeASR:
        async def open_stream(self): pass
        async def send_audio(self,chunk): pass
        async def receive_events(self):
            yield ASRResult(text='I cannot pay. Contact demo@example.test.',confidence=confidence)
        async def close(self): pass
    async def chunks(*args):
        await asyncio.sleep(.03)
        yield AudioChunk(0,b'',0,30,'customer','test annotation',30)
    entry={'fixture_id':'test_replay','duration_ms':30,'language':'en'}
    monkeypatch.setattr('app.api.realtime.catalogue',lambda:[entry])
    path=tmp_path/'fixture.wav';path.touch()
    monkeypatch.setattr('app.api.realtime.public_audio',lambda _:path)
    monkeypatch.setattr('app.realtime.service.role_timeline',lambda _:[])
    monkeypatch.setattr('app.realtime.service.replay_chunks',chunks)
    manager.asr_factory=lambda *args:FakeASR()
    response=client.post('/api/realtime/replays',json={'fixture_id':'test_replay','call_id':'test_realtime'})
    assert response.status_code==201
    assert client.post('/api/realtime/replays',json={'fixture_id':'test_replay'}).status_code==409
    events=[]
    with client.websocket_connect('/ws/calls/test_realtime',headers={'origin':'http://127.0.0.1:5173'}) as ws:
        while True:
            event=ws.receive_json();events.append(event)
            if event['type']=='chunk_complete':ws.send_json({'type':'ack','chunk_id':0})
            if event['type']=='latency':break
    assert any(e['type']=='nudge' for e in events)==(confidence>.37)
    assert 'demo@example.test' not in json.dumps(events)
    assert '[EMAIL_REDACTED]' in json.dumps(events)
    with client.app.state.sessions() as session:
        assert session.scalar(select(LatencySample).where(LatencySample.call_id=='test_realtime')).end_to_end_latency_ms>0
        assert bool(session.scalar(select(Nudge).where(Nudge.call_id=='test_realtime')))==(confidence>.37)
    stopped=client.post('/api/realtime/replays/test_realtime/stop',json={})
    assert stopped.status_code==200
    assert stopped.json()['status']=='stopped' and stopped.json()['playback_finished_ms'] is not None
    class FailedASR(FakeASR):
        async def open_stream(self): raise TimeoutError
    manager.asr_factory=lambda *args:FailedASR()
    assert client.post('/api/realtime/replays',json={'fixture_id':'test_replay','call_id':'failed_realtime'}).status_code==201
    with client.websocket_connect('/ws/calls/failed_realtime') as ws:
        event=ws.receive_json()
        if event['payload']['status']!='failed':event=ws.receive_json()
        assert event['payload']['status']=='failed'
    with client.app.state.sessions() as session:
        assert not session.scalar(select(Nudge).where(Nudge.call_id=='failed_realtime'))

def test_stream_cancellation_kills_worker(settings,monkeypatch):
    from app.providers.streaming_asr import LocalStreamingASR
    async def run():
        worker=SimpleNamespace(returncode=None,killed=False)
        def kill():worker.killed=True;worker.returncode=-1
        async def wait():return -1
        worker.kill=kill;worker.wait=wait
        provider=LocalStreamingASR(settings);provider.process=worker
        await provider.close()
        assert worker.killed
    asyncio.run(run())
