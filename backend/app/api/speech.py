import asyncio
import io
import logging
import wave

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app.schemas.voice import TurnRequest
from app.voice.audio import prepare_audio

router = APIRouter(prefix="/api/voice/calls", tags=["speech"])
logger = logging.getLogger("darwix.speech")


def validate_wave(audio, max_seconds):
    try:
        with wave.open(io.BytesIO(audio)) as file:
            duration = file.getnframes() / file.getframerate()
            if file.getsampwidth() != 2 or file.getnchannels() not in {1, 2} or not 8000 <= file.getframerate() <= 48000 or not 0.1 <= duration <= max_seconds:
                raise ValueError
            if len(file.readframes(file.getnframes())) != file.getnframes() * file.getnchannels() * 2:
                raise ValueError
            return duration
    except Exception:
        raise HTTPException(422, "Supply a valid 16-bit PCM WAV within the allowed duration.") from None


async def limited_body(request, max_bytes):
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > max_bytes:
            raise HTTPException(413, "Audio exceeds the allowed size.")
        body.extend(chunk)
    return bytes(body)


@router.get("/{call_id}/speech/{turn_id}")
async def spoken_reply(call_id: str, turn_id: str, request: Request):
    with request.app.state.sessions() as session:
        call = request.app.state.voice_tools.call(session, call_id)
        reply = call.state.get("greeting") if turn_id == "greeting" else call.state.get("responses", {}).get(turn_id, {}).get("reply")
        if reply is None:
            raise HTTPException(404, "Agent reply not found.")
    try:
        audio = await asyncio.wait_for(request.app.state.tts.synthesize(reply["text"], "en"), request.app.state.settings.provider_timeout_seconds)
        return Response(audio, media_type="audio/wav", headers={"Cache-Control":"no-store"})
    except Exception as exc:
        logger.warning("tts_unavailable", extra={"error_type":type(exc).__name__})
        raise HTTPException(503, "Spoken output is unavailable. Read the displayed agent reply.") from None


@router.post("/{call_id}/audio-turn")
async def audio_turn(call_id: str, request: Request, turn_id: str = Query(pattern=r"^[A-Za-z0-9_-]{1,80}$")):
    with request.app.state.sessions() as session:
        call = request.app.state.voice_tools.call(session, call_id, active=True)
    settings = request.app.state.settings
    audio = await limited_body(request, 5_000_000)
    validate_wave(audio, settings.voice_audio_max_seconds)
    prepared = prepare_audio(audio)
    metrics = prepared.metrics
    if prepared.issue:
        logger.info("asr_input_rejected", extra={**metrics,"reason":prepared.issue,"asr_provider":settings.asr_provider})
        return {"accepted":False,"reason":prepared.issue,"audio":metrics,
                "message":"The selected microphone recorded almost no sound. Choose your laptop microphone below and check that the input meter moves while you speak."}
    try:
        recognized = await asyncio.wait_for(request.app.state.asr.transcribe(prepared.audio), settings.asr_timeout_seconds)
    except Exception as exc:
        logger.warning("asr_unavailable", extra={"error_type":type(exc).__name__})
        return {"accepted":False, "reason":"asr_unavailable", "audio":metrics,
                "message":"Speech recognition is unavailable. Please type your reply or retry; no details were updated."}
    logger.info("asr_result", extra={**metrics,"confidence":recognized.confidence,"asr_provider":settings.asr_provider})
    threshold = settings.whisper_min_score if settings.asr_provider == "whisper" else settings.voice_asr_min_confidence
    if recognized.confidence < threshold or not recognized.text.strip():
        preview = request.app.state.voice_tools.scrub(recognized.text).strip()
        return {"accepted":False, "reason":"unclear_audio", "confidence":recognized.confidence,"audio":metrics,
                "review_required":bool(preview),"review_text":preview,
                "message":"I picked up audio but could not confidently transcribe it. Review the text below before using it; no details were updated." if preview else
                          "I picked up audio but could not transcribe it. Move closer to the microphone and try a short reply, or type it."}
    reply = await request.app.state.voice.process_turn(call_id, TurnRequest(turn_id=turn_id, text=recognized.text, require_confirmation=True))
    return {"accepted":True, "confidence":recognized.confidence,"audio":metrics,
            "transcript":request.app.state.voice_tools.scrub(recognized.text), "reply":reply.model_dump()}


@router.post("/{call_id}/recording")
async def save_recording(call_id: str, request: Request):
    with request.app.state.sessions() as session:
        call = request.app.state.voice_tools.call(session, call_id)
        if not call.consent_obtained or not call.state.get("recording_consent"):
            raise HTTPException(403, "Explicit recording consent and qualification consent are required.")
        audio = await limited_body(request, 40_000_000)
        validate_wave(audio, 1800)
        directory = request.app.state.settings.recordings_dir
        directory.mkdir(parents=True, exist_ok=True)
        # Hash the ID to construct a fixed filename; never use an untrusted path.
        import hashlib
        filename = hashlib.sha256(call_id.encode()).hexdigest() + ".wav"
        (directory / filename).write_bytes(audio)
        call.state = {**call.state, "recording_file":filename}
        session.commit()
        return {"saved":True, "download_url":f"/api/voice/calls/{call_id}/recording"}


@router.get("/{call_id}/recording")
async def get_recording(call_id: str, request: Request):
    with request.app.state.sessions() as session:
        call = request.app.state.voice_tools.call(session, call_id)
        filename = call.state.get("recording_file")
    if not filename:
        raise HTTPException(404, "No recording is saved for this call.")
    from fastapi.responses import FileResponse
    return FileResponse(request.app.state.settings.recordings_dir / filename, media_type="audio/wav", filename="demo-call.wav")
