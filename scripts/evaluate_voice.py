"""Execute synthetic HTTP conversations and render the actual dialogue as WAV.

Recordings use scripted text input and SAPI spoken output. Separate audio probes
exercise ASR and its confidence gate; neither is a human-microphone test.
"""
import argparse
import asyncio
import hashlib
import io
import json
import sys
import time
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import httpx
import numpy as np

from app.config import Settings
from app.providers.windows_speech import WindowsSpeechProvider


def check_reply(name, reply):
    fields = reply["qualification"]["fields"]
    amount = fields["requested_amount"]
    checks = {
        "preliminary_outcome":lambda:reply["eligibility"]["status"] == "preliminarily_qualified" and len(reply["citations"]) >= 4,
        "mock_lead":lambda:bool(reply["lead_id"]) and reply["status"] == "completed",
        "objection_citation":lambda:reply["grounded"] is True and any("demo_objections" in c["source"] for c in reply["citations"]),
        "unknown_fallback":lambda:reply["grounded"] is False and not reply["citations"] and "verified information" in reply["text"],
        "escalation":lambda:bool(reply["escalation_id"]) and reply["status"] == "escalated" and "mock" in reply["text"],
        "missing_amount":lambda:amount["value"] is None and amount["status"] == "missing",
        "tentative_amount":lambda:amount["value"] == 500000 and amount["status"] == "tentative",
        "confirmed_amount":lambda:amount["value"] == 500000 and amount["status"] == "confirmed",
        "conflicting_amount":lambda:amount["value"] == 500000 and amount["status"] == "conflicting" and amount["candidates"] == [500000,600000],
        "resolved_amount":lambda:amount["value"] == 600000 and amount["status"] == "confirmed",
        "callback":lambda:bool(reply["callback_id"]) and "schedule_callback" in reply["tools_called"],
    }
    return bool(checks[name]()) if name else True


def concatenate_waves(clips, target):
    params = None; frames = []; elapsed = 0; timeline = []
    for speaker, utterance, audio in clips:
        with wave.open(io.BytesIO(audio)) as file:
            current = (file.getnchannels(), file.getsampwidth(), file.getframerate())
            if params is not None and params != current:
                raise ValueError("Speech voices returned incompatible audio formats")
            params = current; data = file.readframes(file.getnframes())
            duration = file.getnframes() * 1000 / file.getframerate()
            timeline.append({"speaker":speaker,"text":utterance,"start_ms":round(elapsed),"end_ms":round(elapsed+duration)})
            frames.extend([data, b"\x00" * int(.25 * current[2]) * current[0] * current[1]])
            elapsed += duration + 250
    with wave.open(str(target),"wb") as file:
        file.setnchannels(params[0]); file.setsampwidth(params[1]); file.setframerate(params[2]); file.writeframes(b"".join(frames))
    return timeline, round(elapsed, 2)


def browser_probe(audio):
    """Chrome fake microphone expects 48 kHz; resample only this test fixture."""
    with wave.open(io.BytesIO(audio)) as source:
        samples=np.frombuffer(source.readframes(source.getnframes()),dtype="<i2")
        rate=source.getframerate()
    positions=np.arange(round(len(samples)*48000/rate))*rate/48000
    converted=np.rint(np.interp(positions,np.arange(len(samples)),samples)).astype("<i2")
    stream=io.BytesIO()
    with wave.open(stream,"wb") as target:
        target.setnchannels(1); target.setsampwidth(2); target.setframerate(48000); target.writeframes(converted.tobytes())
    return stream.getvalue()


async def evaluate(args):
    output = ROOT / "evaluations/voice"; audio_dir = ROOT / "data/audio/q1"
    audio_dir.mkdir(parents=True,exist_ok=True)
    # Local speech only. Never read or use an account key in this evidence script.
    customer = WindowsSpeechProvider(Settings(_env_file=None,tts_voice="Microsoft Zira Desktop",provider_timeout_seconds=20))
    cases = json.loads((output / "calls.json").read_text())
    run_id = uuid.uuid4().hex[:8]; results = []; probes = []
    async with httpx.AsyncClient(base_url=args.base_url,timeout=30) as client:
        async def post(path, body):
            response = await client.post(path,json=body); response.raise_for_status(); return response.json()
        async def agent_audio(call, reply):
            response=await client.get(f"/api/voice/calls/{call}/speech/{reply['turn_id']}")
            response.raise_for_status(); return response.content
        for case in cases:
            call=f"q1_{case['fixture_id']}_{run_id}"
            reply=await post("/api/voice/calls",{"call_id":call})
            clips=[]; exchanges=[]
            if not args.without_audio: clips.append(("agent",reply["text"],await agent_audio(call,reply)))
            for i, turn in enumerate(case["turns"]):
                reply=await post(f"/api/voice/calls/{call}/turn",{"turn_id":f"turn_{i+1}","text":turn["text"]})
                exchanges.append({"customer_text":turn["text"],"input_mode":"scripted_text","expected_check":turn.get("check"),
                    "observed_reply":reply,"passed":check_reply(turn.get("check"),reply)})
                if not args.without_audio:
                    clips.append(("customer",turn["text"],await customer.synthesize(turn["text"])))
                    clips.append(("agent",reply["text"],await agent_audio(call,reply)))
            path=audio_dir/f"{case['fixture_id']}.wav"
            timeline,duration=concatenate_waves(clips,path) if clips else ([],None)
            snapshot=await client.get(f"/api/voice/calls/{call}"); snapshot.raise_for_status()
            report={**case,"call_id":call,"audio":path.relative_to(ROOT).as_posix() if clips else None,
                "audio_kind":"Synthesized scripted dialogue; not a human microphone call", "audio_duration_ms":duration,
                "audio_sha256":hashlib.sha256(path.read_bytes()).hexdigest() if clips else None,
                "audio_timeline":timeline,"persisted_redacted_transcript":snapshot.json()["transcript"],
                "exchanges":exchanges,"passed":all(t["passed"] for t in exchanges)}
            transcript_path=output/f"{case['fixture_id']}.json"
            transcript_path.write_text(json.dumps(report,indent=2)+"\n")
            results.append({"fixture_id":case["fixture_id"],"scenario_ids":case["scenario_ids"],"passed":report["passed"],
                "audio":report["audio"],"transcript":transcript_path.relative_to(ROOT).as_posix(),"duration_ms":duration})
            print(json.dumps({"call":case["fixture_id"],"passed":report["passed"],"audio":report["audio"]}),flush=True)
        if not args.without_audio:
            agent=WindowsSpeechProvider(Settings(_env_file=None,provider_timeout_seconds=20))
            for i, (utterance, expected, setup) in enumerate([
                ("Yes.","active",False), ("Five hundred thousand.","amount",True),
                ("Retail.","business_type",True), ("Forty eight months.","business_age",True),
                ("What is the processing fee?","grounded_faq",True), ("I want a human representative.","escalated",True),
            ]):
                call=f"q1_probe_{i}_{run_id}"; await post("/api/voice/calls",{"call_id":call})
                if setup: await post("/api/voice/consent",{"call_id":call,"consent":True})
                audio=await agent.synthesize(utterance); path=audio_dir/f"probe_{i+1}.wav"; path.write_bytes(audio)
                if expected=="grounded_faq": (audio_dir/"probe_browser_faq.wav").write_bytes(browser_probe(audio))
                started=time.perf_counter()
                response=await client.post(f"/api/voice/calls/{call}/audio-turn?turn_id=probe",content=audio,headers={"Content-Type":"audio/wav"})
                response.raise_for_status(); observed=response.json()
                accepted=observed.get("accepted",False); reply=observed.get("reply",{})
                fields=reply.get("qualification",{}).get("fields",{})
                correct=accepted and (
                    reply.get("status")==expected if expected in {"active","escalated"} else
                    reply.get("grounded") is True if expected=="grounded_faq" else
                    fields.get("requested_amount",{}).get("value")==500000 if expected=="amount" else
                    fields.get("business_type",{}).get("value","").casefold()=="retail" if expected=="business_type" else
                    fields.get("business_age_months",{}).get("value")==48)
                probes.append({"input_text":utterance,"expected_behavior":expected,"audio":path.relative_to(ROOT).as_posix(),
                    "observed":observed,"expected_behavior_reached":bool(correct),"request_duration_ms":round((time.perf_counter()-started)*1000,2)})
        runtime_settings=Settings()
        asr_label=f"Local Whisper {runtime_settings.whisper_model_name} CPU int8" if runtime_settings.asr_provider=="whisper" else "Windows System.Speech en-US unrestricted dictation"
        summary={"generated_at":datetime.now(timezone.utc).isoformat(),"base_url":args.base_url,"calls":results,
            "asr_provider":asr_label, "tts_agent":"Microsoft David Desktop",
            "tts_customer":"Microsoft Zira Desktop","audio_probes":probes,
            "manual_validation_pending":"Human microphone quality, live recording and native-speaker assessment have not been performed."}
        (output/"results.json").write_text(json.dumps(summary,indent=2)+"\n")
        lines=["# Q1 Phase 2 results","","Generated from actual HTTP tool/controller replies and local speech providers. All data is synthetic.","",
            "The three WAV recordings render executed scripted-text conversations. They are synthesized dialogue, not human microphone calls. Separate WAV probes pass through the actual ASR endpoint.","",
            "| Recording | Scenarios | Observed result | Audio / transcript |","|---|---|---|---|"]
        for result in results:
            audio=f"[WAV](../{result['audio']})" if result['audio'] else "not generated"
            lines.append(f"| {result['fixture_id']} | {', '.join(result['scenario_ids'])} | {'pass' if result['passed'] else 'fail'} | {audio}, [JSON](../{result['transcript']}) |")
        lines += ["","Expected scenarios: [A-E definitions](../evaluations/voice/scenarios.json). Each transcript includes expected checks, complete observed replies, sources, tool names, pass/fail and an audio timeline.","",
            "## Speech observations","","| Synthetic input | Accepted | ASR confidence | Intended behavior reached |","|---|---|---|---|"]
        for probe in probes:
            observed=probe['observed']; confidence=observed.get('confidence')
            lines.append(f"| {probe['input_text']} | {observed.get('accepted')} | {confidence:.3f} | {probe['expected_behavior_reached']} |" if confidence is not None else f"| {probe['input_text']} | False | unavailable | False |")
        lines += ["",f"Actual accepted speech probes: {sum(p['observed'].get('accepted',False) for p in probes)}/{len(probes)}. Intended behavior reached: {sum(p['expected_behavior_reached'] for p in probes)}/{len(probes)}. This small synthesized set is not an accuracy benchmark.","",
            f"ASR: {asr_label}. Scores below the configured provider threshold require review/repetition without changing qualification. Windows confidence and Whisper decoder scores are not equivalent or calibrated accuracy. The probe JSON records real recognition output and measured HTTP request duration; these are not Q4 component-latency samples.","",
            "## Manual validation still required","","- Open `/call`, allow microphone access, use a headset and exercise a live spoken FAQ and qualification flow.",
            "- Check the recording-consent box, consent to qualification, complete/end a synthetic call and download its WAV. Public synthetic evidence does not replace human microphone testing.",
            "- Windows English speech components must be installed. Cross-platform/native-language voice providers and Q4 streaming remain outside Phase 2.",
            "- Lead, callback and escalation tools write mock local records. A human must coordinate a real callback; this app never contacts anyone.",
            "- Hosted LLM interpretation is optional and tested with mocks only. No hosted calls were made for these results.",""]
        (ROOT/"docs/q1-results.md").write_text("\n".join(lines))
        return 0 if all(r['passed'] for r in results) else 1


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url",default="http://127.0.0.1:8000")
    parser.add_argument("--without-audio",action="store_true",help="Controller-only evaluation on machines without Windows speech")
    try:
        sys.exit(asyncio.run(evaluate(parser.parse_args())))
    except Exception as exc:
        print(json.dumps({"status":"failed","error_type":type(exc).__name__,"manual_action":"Check running backend, ingested KB and Windows English speech components."}))
        sys.exit(1)
