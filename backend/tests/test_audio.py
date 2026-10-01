import asyncio
import io
import json
import wave
from types import SimpleNamespace

import numpy as np
import pytest

from app.providers.whisper_asr import WhisperASRProvider
from app.providers.whisper_worker import transcribe
from app.voice.audio import prepare_audio


def wave_bytes(samples, rate=48000, channels=1):
    stream=io.BytesIO()
    with wave.open(stream,"wb") as target:
        target.setnchannels(channels); target.setsampwidth(2); target.setframerate(rate)
        target.writeframes(np.rint(samples*32767).astype("<i2").tobytes())
    return stream.getvalue()


def test_silent_microphone_never_reaches_asr(client,monkeypatch):
    call=client.post("/api/voice/calls",json={}).json()["call_id"]
    async def unexpected(audio): raise AssertionError("silent audio must not reach a recognizer")
    monkeypatch.setattr(client.app.state.asr,"transcribe",unexpected)
    response=client.post(f"/api/voice/calls/{call}/audio-turn?turn_id=silent",content=wave_bytes(np.zeros(48000))).json()
    assert response["accepted"] is False and response["reason"] == "no_audio_input"
    assert "input meter" in response["message"]
    assert client.get(f"/api/voice/calls/{call}").json()["status"] == "awaiting_consent"


def test_quiet_stereo_audio_is_conditioned_with_bounded_gain():
    voice=.003*np.sin(2*np.pi*300*np.arange(48000)/48000)
    with_silence=np.concatenate([np.zeros(48000),voice,np.zeros(48000)])
    stereo=np.stack([with_silence,with_silence],axis=1)
    prepared=prepare_audio(wave_bytes(stereo,channels=2))
    assert prepared.issue is None and prepared.metrics["normalization_gain"] == 8
    with wave.open(io.BytesIO(prepared.audio)) as source:
        assert source.getframerate() == 16000 and source.getnchannels() == 1
        assert 1 <= source.getnframes()/16000 < 1.4
        output=np.frombuffer(source.readframes(source.getnframes()),dtype="<i2")/32768
        assert .02 < max(abs(output)) < .025


def test_normalization_preserves_real_speech_and_does_not_clip():
    samples=.98*np.sin(2*np.pi*400*np.arange(32000)/16000)
    prepared=prepare_audio(wave_bytes(samples,rate=16000))
    assert prepared.issue is None and prepared.metrics["normalization_gain"] < 1
    with wave.open(io.BytesIO(prepared.audio)) as source:
        output=np.frombuffer(source.readframes(source.getnframes()),dtype="<i2")/32768
        assert max(abs(output)) <= .901


def test_low_confidence_preview_is_redacted_without_state_change(client,monkeypatch):
    from app.schemas.voice import ASRResult
    call=client.post("/api/voice/calls",json={}).json()["call_id"]
    async def recognize(audio): return ASRResult(text="Email demo@example.test",confidence=.2)
    monkeypatch.setattr(client.app.state.asr,"transcribe",recognize)
    samples=.1*np.sin(2*np.pi*400*np.arange(16000)/16000)
    result=client.post(f"/api/voice/calls/{call}/audio-turn?turn_id=review",content=wave_bytes(samples,16000)).json()
    assert result["review_required"] is True and "[EMAIL_REDACTED]" in result["review_text"]
    assert "demo@example.test" not in json.dumps(result)
    snapshot=client.get(f"/api/voice/calls/{call}").json()
    assert len(snapshot["transcript"]) == 1 and snapshot["status"] == "awaiting_consent"


@pytest.mark.parametrize("provider,accepted",[("windows",False),("whisper",True)])
def test_provider_score_scales_are_separate_and_spoken_details_still_need_confirmation(client,monkeypatch,provider,accepted):
    from app.schemas.voice import ASRResult
    call=client.post("/api/voice/calls",json={}).json()["call_id"]
    client.post("/api/voice/consent",json={"call_id":call,"consent":True})
    client.app.state.settings.asr_provider=provider
    async def recognize(audio): return ASRResult(text="500000",confidence=.45)
    monkeypatch.setattr(client.app.state.asr,"transcribe",recognize)
    samples=.1*np.sin(2*np.pi*400*np.arange(16000)/16000)
    result=client.post(f"/api/voice/calls/{call}/audio-turn?turn_id=score_scale",content=wave_bytes(samples,16000)).json()
    assert result["accepted"] is accepted
    if accepted:
        assert result["reply"]["qualification"]["fields"]["requested_amount"]["status"] == "tentative"
    else:
        assert result["review_required"] is True


def test_whisper_missing_model_fails_safely(settings,tmp_path):
    settings.whisper_model_dir=tmp_path/"not_downloaded"
    with pytest.raises(RuntimeError,match="setup_asr"):
        asyncio.run(WhisperASRProvider(settings).transcribe(b"unused"))


def test_whisper_worker_rejects_no_speech_and_repetition():
    class Model:
        def transcribe(self,audio,**options):
            assert options["condition_on_previous_text"] is False
            assert options["language"] == "en" and options["vad_filter"] is True
            return iter([
                SimpleNamespace(text="Thank you for watching",avg_logprob=-.1,no_speech_prob=.9,compression_ratio=1),
                SimpleNamespace(text="loop loop loop",avg_logprob=-.1,no_speech_prob=.1,compression_ratio=3),
                SimpleNamespace(text="Retail.",avg_logprob=-.2,no_speech_prob=.1,compression_ratio=1),
            ]),None
    result=transcribe(Model(),"private_temp_audio.wav")
    assert result["text"] == "Retail." and .8 < result["confidence"] < .9


@pytest.mark.parametrize("failure",["timeout","cancel"])
def test_whisper_provider_kills_and_reaps_worker(settings,tmp_path,monkeypatch,failure):
    settings.whisper_model_dir=tmp_path
    (tmp_path/"model.bin").write_bytes(b"mock model")
    settings.asr_timeout_seconds=.01
    class Process:
        returncode=None
        killed=False
        reaped=False
        async def wait(self):
            if self.killed:
                self.reaped=True; self.returncode=-1; return -1
            await asyncio.sleep(10)
        def kill(self): self.killed=True
    process=Process()
    async def create(*args,**kwargs):
        assert "-m" in args and kwargs["stdout"] == asyncio.subprocess.DEVNULL
        return process
    monkeypatch.setattr(asyncio,"create_subprocess_exec",create)
    async def run():
        task=asyncio.create_task(WhisperASRProvider(settings).transcribe(b"private temporary input"))
        if failure=="cancel":
            await asyncio.sleep(.005); task.cancel()
        with pytest.raises(asyncio.CancelledError if failure=="cancel" else TimeoutError): await task
        assert process.killed and process.reaped
    asyncio.run(run())
