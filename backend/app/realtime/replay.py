"""Bounded, clock-paced reads. Reference words never enter ASR or detection."""
import asyncio
import io
import json
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from app.config import ROOT

@dataclass
class AudioChunk:
    chunk_id: int
    audio: bytes
    start_ms: int
    end_ms: int
    speaker: str
    speaker_source: str
    received_ms: float = 0

def catalogue():
    path = ROOT / 'data/fixtures/replays.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else []

def public_audio(entry):
    path = (ROOT / entry['audio']).resolve()
    public_root = (ROOT / 'data/audio').resolve()
    if not path.is_relative_to(public_root) or path.is_relative_to(public_root / 'private') or path.suffix != '.wav':
        raise ValueError('invalid_public_recording')
    return path

def speaker_for(timeline, start, end):
    overlaps = {}
    for turn in timeline:
        speaker = turn['speaker']
        overlaps[speaker] = overlaps.get(speaker, 0) + max(0, min(end, turn['end_ms']) - max(start, turn['start_ms']))
    # Offline role annotations are allowed only for registered synthetic fixtures.
    # Require one role and meaningful speech overlap; never infer a role from words.
    roles = {role for role, overlap in overlaps.items() if overlap > 0 and role in {'agent','customer'}}
    if len(roles) == 1:
        return roles.pop(), 'registered synthetic recording role annotation; no diarization'
    return 'unknown', 'unknown; diarization unavailable or mixed-role chunk'

async def replay_chunks(entry, chunk_seconds, origin, timeline=()):
    with wave.open(str(public_audio(entry)), 'rb') as source:
        rate = source.getframerate()
        if source.getnchannels() != 1 or source.getsampwidth() != 2 or not 8000 <= rate <= 48000:
            raise ValueError('replay_requires_mono_pcm16')
        if not 0 < source.getnframes() / rate <= 600: raise ValueError('recording_duration_invalid')
        position, index = 0, 0
        while position < source.getnframes():
            frames = source.readframes(round(chunk_seconds * rate))
            if not frames: raise ValueError('truncated_recording')
            start = round(position * 1000 / rate)
            position += len(frames) // 2
            end = round(position * 1000 / rate)
            # A chunk is available only after its audio duration has elapsed.
            await asyncio.sleep(max(0, origin + end / 1000 - time.perf_counter()))
            output = io.BytesIO()
            with wave.open(output, 'wb') as target:
                target.setnchannels(1); target.setsampwidth(2); target.setframerate(rate); target.writeframes(frames)
            role, provenance = speaker_for(timeline, start, end)
            yield AudioChunk(index, output.getvalue(), start, end, role, provenance,
                             (time.perf_counter() - origin) * 1000)
            index += 1

def role_timeline(entry):
    if not entry.get('annotations'): return []
    path = (ROOT / entry['annotations']).resolve()
    if not path.is_relative_to((ROOT / 'evaluations').resolve()): raise ValueError('invalid_annotations')
    document = json.loads(path.read_text(encoding='utf-8'))
    # Only inspect the WAV header before playback. Checksums are evaluation
    # provenance, not a reason to read the complete recording before streaming.
    with wave.open(str(public_audio(entry)), 'rb') as source:
        duration=source.getnframes()*1000/source.getframerate()
    declared=document.get('duration_ms',document.get('audio_duration_ms',0))
    if document.get('audio') != entry['audio'] or abs(declared-duration)>10:
        raise ValueError('annotation_audio_mismatch')
    return [{key: turn[key] for key in ('speaker','start_ms','end_ms')} for turn in document['audio_timeline']]
