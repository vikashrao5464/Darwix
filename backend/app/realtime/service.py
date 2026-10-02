import asyncio
import logging
import time
import uuid
from sqlalchemy import select
from app.db.models import Call, TranscriptSegment, Signal, Nudge, LatencySample
from app.knowledge.pii import redact_pii
from app.providers.streaming_asr import LocalStreamingASR
from app.realtime.events import EventHub
from app.realtime.latency import sample, summarize
from app.realtime.nudges import make_nudge
from app.realtime.replay import role_timeline, replay_chunks
from app.realtime.signals import SignalDetector
from app.realtime.suppression import Suppression
from app.realtime.transcription import RollingTranscript
from app.schemas.realtime import Transcript

logger=logging.getLogger('darwix.realtime')

class ReplayJob:
    def __init__(self, manager, call_id, entry):
        self.manager, self.call_id, self.entry = manager, call_id, entry
        self.settings=manager.settings
        self.hub=EventHub(self.settings.realtime_max_subscribers)
        self.origin=None
        self.status='preparing'
        self.pending={}
        self.counts={'chunks':0,'asr_failures':0,'unacknowledged':0,'nudges':0,'queue_high_water':0}
        self.suppressions=[]
        self.samples=[]
        self.timeline=RollingTranscript(self.settings.realtime_window_seconds)
        self.suppression=Suppression(self.settings)
        self.detector=SignalDetector(self.settings, manager.llm)
        self.duration_ms=entry['duration_ms']
        self.playback_finished_ms=None
        self.task=None
        self.error=None
    def now(self): return (time.perf_counter()-self.origin)*1000 if self.origin else 0
    async def state(self, status):
        self.status=status
        with self.manager.sessions() as session:
            call=session.get(Call,self.call_id)
            call.status=status
            call.state={'realtime':True,'fixture_id':self.entry['fixture_id'],'duration_ms':self.duration_ms,
                'counts':dict(self.counts),'error':self.error,'playback_finished_ms':self.playback_finished_ms,
                'suppression_count':len(self.suppressions)}
            session.commit()
        await self.hub.publish('status',self.info())
    def info(self):
        return {'call_id':self.call_id,'fixture_id':self.entry['fixture_id'],'status':self.status,
            'duration_ms':self.duration_ms,'elapsed_ms':round(self.now()),'counts':dict(self.counts),
            'error':self.error,'playback_finished_ms':self.playback_finished_ms}
    def snapshot(self):
        with self.manager.sessions() as session:
            transcripts=session.scalars(select(TranscriptSegment).where(TranscriptSegment.call_id==self.call_id)
                .order_by(TranscriptSegment.start_ms)).all()
            signals=session.scalars(select(Signal).where(Signal.call_id==self.call_id)).all()
            nudges=session.scalars(select(Nudge).where(Nudge.call_id==self.call_id)).all()
            def row(value): return {col.name:getattr(value,col.name) for col in value.__table__.columns}
            return {**self.info(),'transcripts':[row(t) for t in transcripts[-40:]],
                'signals':[row(s) for s in signals[-40:]],'nudges':[row(n) for n in nudges if n.expires_at_ms>self.now()],
                'latency':summarize(self.samples), 'suppression':self.suppressions[-40:]}
    async def acknowledge(self, chunk_id):
        stamps=self.pending.pop(chunk_id,None)
        if not stamps: return
        delivered=self.now()
        if delivered-stamps[-1] > self.settings.realtime_ack_timeout_seconds*1000:
            self.counts['unacknowledged']+=1; return
        measured=sample(self.call_id,chunk_id,*stamps,delivered)
        with self.manager.sessions() as session:
            session.add(LatencySample(**measured)); session.commit()
        self.samples.append(measured)
        await self.hub.publish('latency',measured)
    async def run(self):
        processor=None
        language=self.entry.get('language','en')
        settings=self.settings
        if language != 'en':
            settings=settings.model_copy(update={'whisper_model_dir':settings.localization_whisper_model_dir,
                'asr_timeout_seconds':settings.localization_asr_timeout_seconds})
        asr=self.manager.asr_factory(settings,language)
        queue=asyncio.Queue(maxsize=self.settings.realtime_queue_size)
        try:
            timeline=await asyncio.to_thread(role_timeline,self.entry)
            await asr.open_stream()
            self.origin=time.perf_counter()
            await self.state('replaying')
            processor=asyncio.create_task(self.analyze(queue,asr))
            async for chunk in replay_chunks(self.entry,self.settings.realtime_chunk_seconds,self.origin,timeline):
                # Bound backlog instead of buffering a full call or hiding overload.
                if processor.done(): await processor
                await asyncio.wait_for(queue.put(chunk),self.settings.realtime_chunk_seconds)
                self.counts['queue_high_water']=max(self.counts['queue_high_water'],queue.qsize())
            self.playback_finished_ms=self.now()
            await self.state('draining')
            if processor.done(): await processor
            await asyncio.wait_for(queue.put(None),self.settings.realtime_chunk_seconds)
            await processor
            if self.pending: await asyncio.sleep(self.settings.realtime_ack_timeout_seconds)
            self.counts['unacknowledged']+=len(self.pending)
            self.pending.clear()
            await self.state('completed')
        except asyncio.CancelledError:
            if self.playback_finished_ms is None:
                self.playback_finished_ms=min(self.now(),self.duration_ms)
            await self.state('stopped')
            raise
        except Exception as exc:
            self.error='Replay analysis is unavailable or cannot keep up. Check local models and retry.'
            logger.warning('replay_failed',extra={'call_id':self.call_id,'error_type':type(exc).__name__})
            await self.state('failed')
        finally:
            if processor and not processor.done():
                processor.cancel()
                await asyncio.gather(processor,return_exceptions=True)
            await asr.close()
    async def analyze(self, queue, asr):
        while True:
            chunk=await queue.get()
            if chunk is None: return
            self.counts['chunks']+=1
            result=None
            try:
                await asr.send_audio(chunk.audio)
                result=await anext(asr.receive_events())
            except asyncio.CancelledError: raise
            except Exception as exc:
                self.counts['asr_failures']+=1
                await self.hub.publish('warning',{'chunk_id':chunk.chunk_id,'reason':'ASR unavailable; no nudge generated.'})
                # A dead stream cannot safely consume subsequent chunks.
                raise RuntimeError('stream_asr_failed') from exc
            asr_done=self.now()
            # Shared redaction applies before storage, event delivery and model context.
            redacted=redact_pii(result.text,self.settings.government_id_patterns).redacted_text
            segment=Transcript(chunk_id=chunk.chunk_id,speaker=chunk.speaker,speaker_source=chunk.speaker_source,
                text=redacted,start_ms=chunk.start_ms,end_ms=chunk.end_ms,confidence=result.confidence,
                usable=bool(redacted and result.confidence >= self.settings.whisper_min_score))
            candidates=[]
            if segment.usable:
                self.timeline.add(segment)
                candidates=await self.detector.detect(segment,self.timeline.context())
            elif segment.text:
                await self.hub.publish('warning',{'chunk_id':chunk.chunk_id,'reason':'Uncertain ASR; signals withheld.'})
            signal_done=self.now()
            accepted=[]; nudges=[]
            for candidate in sorted(candidates,key=lambda c:(c.priority!='high',-c.confidence)):
                reason=self.suppression.check(candidate,self.now())
                if reason:
                    withheld={'chunk_id':chunk.chunk_id,'type':candidate.type,'reason':reason,'confidence':candidate.confidence}
                    self.suppressions.append(withheld)
                    await self.hub.publish('suppressed',withheld)
                    continue
                candidate.priority='high' if candidate.type in {'compliance_risk','payment_difficulty'} else 'medium'
                signal={**candidate.model_dump(),'signal_id':'sig_'+uuid.uuid4().hex,'call_id':self.call_id,
                    'detected_at_ms':round(self.now())}
                accepted.append(signal)
                nudges.append(make_nudge(signal,self.now(),self.settings.realtime_nudge_expiry_seconds))
            nudge_done=self.now()
            with self.manager.sessions() as session:
                session.add(TranscriptSegment(segment_id=f'{self.call_id}_chunk_{chunk.chunk_id}',call_id=self.call_id,
                    speaker=segment.speaker,text=segment.text,start_ms=segment.start_ms,end_ms=segment.end_ms,final=True))
                for signal in accepted: session.add(Signal(**signal))
                session.flush()
                for nudge in nudges: session.add(Nudge(**nudge))
                session.commit()
            await self.hub.publish('transcript',segment.model_dump())
            for signal in accepted: await self.hub.publish('signal',signal)
            for nudge in nudges:
                self.counts['nudges']+=1
                await self.hub.publish('nudge',nudge)
            self.pending[chunk.chunk_id]=(chunk.received_ms,asr_done,signal_done,nudge_done)
            # Receipt ack is required for measured delivery; no zero-latency fabrication.
            await self.hub.publish('chunk_complete',{'chunk_id':chunk.chunk_id})

class RealtimeManager:
    def __init__(self,settings,sessions,llm):
        self.settings,self.sessions,self.llm=settings,sessions,llm
        self.jobs={}
        self.asr_factory=LocalStreamingASR
    def start(self,entry,call_id):
        if any(job.status in {'preparing','replaying','draining'} for job in self.jobs.values()):
            raise ValueError('A replay is already running. Stop it before starting another.')
        if len(self.jobs)>=32:
            oldest=next(iter(self.jobs)); self.jobs.pop(oldest).hub.disconnect_all('replay_history_evicted')
        with self.sessions() as session:
            if session.get(Call,call_id): raise ValueError('Call ID already exists. Use a new ID.')
            session.add(Call(call_id=call_id,product='realtime_demo',language=entry.get('language','en'),
                status='preparing',consent_obtained=True,state={'realtime':True,'fixture_id':entry['fixture_id']}))
            session.commit()
        job=ReplayJob(self,call_id,entry)
        self.jobs[call_id]=job
        job.task=asyncio.create_task(job.run())
        return job
    async def close(self):
        for job in self.jobs.values():
            if job.task and not job.task.done(): job.task.cancel()
        await asyncio.gather(*(job.task for job in self.jobs.values() if job.task),return_exceptions=True)
