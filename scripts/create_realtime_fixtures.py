"""Synthetic Q1 stress recording. Unsafe agent lines are evaluation injections."""
import asyncio
import hashlib
import io
import json
import sys
import wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config import Settings
from app.providers.windows_speech import WindowsSpeechProvider

async def create():
    out=ROOT/'evaluations/realtime'; out.mkdir(parents=True,exist_ok=True)
    target=ROOT/'data/audio/q4/q1_insights.wav'; target.parent.mkdir(parents=True,exist_ok=True)
    rate=16000; pcm=np.zeros(rate*66,dtype='<i2')
    timeline=[]
    # Reuse actual recorded Q1 greeting/consent audio and its timeline.
    source=json.loads((ROOT/'evaluations/voice/cooperative.json').read_text(encoding='utf-8'))
    with wave.open(str(ROOT/source['audio']),'rb') as original:
        data=np.frombuffer(original.readframes(original.getframerate()*12),dtype='<i2')
        converted=np.interp(np.arange(rate*12)*original.getframerate()/rate,np.arange(len(data)),data)
        pcm[:rate*12]=np.rint(converted).astype('<i2')
    timeline.extend([dict(t) for t in source['audio_timeline'] if t['start_ms']<12000 and t['end_ms']<=12000])
    voices={role:WindowsSpeechProvider(Settings(_env_file=None,tts_voice=voice,provider_timeout_seconds=20))
        for role,voice in [('agent','Microsoft David Desktop'),('customer','Microsoft Zira Desktop')]}
    definitions=[
      (12,'customer','I need another vehicle for my business.',['missed_opportunity']),
      (18,'agent','Your approval is guaranteed. No credit check is needed.',['compliance_risk']),
      (24,'customer','I already told you twice. This is frustrating.',['rising_frustration']),
      (30,'customer','I cannot pay. Please call me back.',['payment_difficulty','callback_need']),
      (36,'customer','I cannot pay. Please call me back.',[]),
      (48,'customer','Maybe another option. I am not sure.',[]),
      (54,'agent','I can explain the process and arrange a callback.',[]),
    ]
    expected=[]
    for start,role,text,types in definitions:
        audio=await voices[role].synthesize(text)
        with wave.open(io.BytesIO(audio),'rb') as clip:
            samples=np.frombuffer(clip.readframes(clip.getnframes()),dtype='<i2')
            positions=np.arange(round(len(samples)*rate/clip.getframerate()))*clip.getframerate()/rate
            samples=np.rint(np.interp(positions,np.arange(len(samples)),samples)).astype('<i2')
        if len(samples)>rate*5.7: raise ValueError('Speech exceeds six-second fixture slot')
        pcm[start*rate:start*rate+len(samples)]=samples
        timeline.append({'speaker':role,'text':text,'start_ms':start*1000,'end_ms':round(start*1000+len(samples)*1000/rate)})
        expected.append({'chunk_id':start//6,'types':types,'description':text,
            'expect_suppression':'duplicate' if start==36 else 'low_confidence' if start==48 else None})
    # Seeded broadband noise, not speech, in a separate weak-evidence window.
    pcm[42*rate:48*rate]=np.random.default_rng(2026).integers(-2000,2001,rate*6,dtype=np.int16)
    expected.append({'chunk_id':7,'types':[],'description':'Broadband noise; no intelligible utterance'})
    with wave.open(str(target),'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(rate);output.writeframes(pcm.tobytes())
    record={'audio':target.relative_to(ROOT).as_posix(),'audio_kind':'Synthetic Q1 stress recording: actual Q1 opening plus scripted SAPI speech; not a human call',
        'unsafe_agent_lines':'Deliberately injected evaluation phrases, not controller replies or valid business policy.',
        'audio_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'audio_timeline':timeline,'duration_ms':66000,
        'expected':sorted(expected,key=lambda x:x['chunk_id'])}
    (out/'q1_insights-source.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    entries=[{'fixture_id':'q1_insights','title':'Q1 stress call: opportunity, compliance, frustration, payment and noise',
        'audio':record['audio'],'annotations':'evaluations/realtime/q1_insights-source.json','duration_ms':66000,'language':'en','synthetic':True},
        {'fixture_id':'q1_cooperative','title':'Original Q1 cooperative qualification recording','audio':source['audio'],
        'annotations':'evaluations/voice/cooperative.json','duration_ms':round(source['audio_duration_ms']),'language':'en','synthetic':True}]
    (ROOT/'data/fixtures/replays.json').write_text(json.dumps(entries,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'recording':record['audio'],'duration_ms':66000,'fixtures':len(entries)}))
if __name__=='__main__':asyncio.run(create())
