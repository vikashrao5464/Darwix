"""Reproduce synthetic microphone checks; these are not human-accuracy scores."""
import argparse
import asyncio
import io
import json
import sys
import time
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"backend"))
from app.config import Settings
from app.providers.whisper_asr import WhisperASRProvider
from app.voice.audio import prepare_audio
import httpx
import numpy as np


def attenuate(audio,factor):
    with wave.open(io.BytesIO(audio)) as source:
        params=source.getparams()
        samples=np.frombuffer(source.readframes(source.getnframes()),dtype="<i2")
    stream=io.BytesIO()
    with wave.open(stream,"wb") as target:
        target.setparams(params)
        target.writeframes(np.rint(samples*factor).astype("<i2").tobytes())
    return stream.getvalue()


async def compare_models():
    results=[]
    for name in ("base.en","small.en"):
        settings=Settings(_env_file=None,whisper_model_dir=ROOT/f"data/state/models/whisper-{name}")
        provider=WhisperASRProvider(settings)
        for sample in ("probe_1.wav","probe_2.wav","probe_4.wav","probe_5.wav"):
            prepared=prepare_audio((ROOT/"data/audio/q1"/sample).read_bytes())
            started=time.perf_counter(); result=await provider.transcribe(prepared.audio)
            entry={"model":name,"sample":sample,"result":result.model_dump(),"request_ms":round((time.perf_counter()-started)*1000)}
            results.append(entry); print(json.dumps(entry),flush=True)
    (ROOT/"evaluations/voice/asr-model-comparison.json").write_text(json.dumps({
        "audio_kind":"synthetic speech, not human accuracy benchmark","results":results},indent=2)+"\n")
    return 0


async def evaluate(base_url):
    results=[]
    async with httpx.AsyncClient(base_url=base_url,timeout=40) as client:
        for name,sample,factor,expected in (
            ("consent","probe_1.wav",1,"active"),
            ("quiet_consent","probe_1.wav",.04,"active"),
            ("quiet_faq","probe_5.wav",.04,"grounded"),
            ("amount","probe_2.wav",1,"amount"),
        ):
            response=await client.post("/api/voice/calls",json={}); response.raise_for_status()
            call=response.json()["call_id"]
            if expected!="active":
                response=await client.post("/api/voice/consent",json={"call_id":call,"consent":True}); response.raise_for_status()
            audio=(ROOT/"data/audio/q1"/sample).read_bytes()
            if factor!=1: audio=attenuate(audio,factor)
            started=time.perf_counter()
            response=await client.post(f"/api/voice/calls/{call}/audio-turn?turn_id=probe",content=audio)
            response.raise_for_status(); observed=response.json(); reply=observed.get("reply",{})
            if expected=="active": passed=reply.get("status")=="active"
            elif expected=="grounded": passed=reply.get("grounded") is True and bool(reply.get("citations"))
            else:
                field=reply.get("qualification",{}).get("fields",{}).get("requested_amount",{})
                passed=field.get("value")==500000 and field.get("status")=="tentative"
            results.append({"case":name,"source":f"data/audio/q1/{sample}","amplitude_factor":factor,
                "expected":expected,"passed":passed,"request_ms":round((time.perf_counter()-started)*1000),"observed":observed})
            print(json.dumps({"case":name,"accepted":observed["accepted"],"score":observed.get("confidence"),"passed":passed}),flush=True)
    settings=Settings()
    report={"provider":settings.asr_provider,"model":settings.whisper_model_name,"threshold":settings.whisper_min_score,
        "score_kind":"decoder evidence, not calibrated accuracy",
        "audio_kind":"Synthetic WAV probes; human microphone validation separate","results":results}
    (ROOT/"evaluations/voice/microphone-fix.json").write_text(json.dumps(report,indent=2)+"\n")
    return 0 if all(result["passed"] for result in results) else 1


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url",default="http://127.0.0.1:8000")
    parser.add_argument("--compare-models",action="store_true",help="Requires both prepared local models")
    args=parser.parse_args()
    try:
        sys.exit(asyncio.run(compare_models() if args.compare_models else evaluate(args.base_url)))
    except Exception as exc:
        print(json.dumps({"status":"failed","error_type":type(exc).__name__,
            "manual_action":"Check the running backend, synthetic fixtures and prepared local ASR model."}))
        sys.exit(1)
