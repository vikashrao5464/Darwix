"""PCM conditioning and signal diagnostics; never persist microphone samples."""
import io
import math
import wave
from dataclasses import dataclass

import numpy as np


@dataclass
class PreparedAudio:
    audio: bytes
    metrics: dict
    issue: str | None = None


def prepare_audio(audio: bytes) -> PreparedAudio:
    with wave.open(io.BytesIO(audio)) as source:
        rate = source.getframerate()
        channels = source.getnchannels()
        samples = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(np.float64) / 32768
    samples = samples.reshape(-1, channels).mean(axis=1)
    rms = float(np.sqrt(np.mean(samples * samples)))
    peak = float(np.max(np.abs(samples)))
    metrics = {"audio_duration_ms":round(len(samples) * 1000 / rate),
        "audio_rms_dbfs":round(20 * math.log10(max(rms, 1e-8)), 1),
        "audio_peak_dbfs":round(20 * math.log10(max(peak, 1e-8)), 1),
        "clipping_fraction":round(float(np.mean(np.abs(samples) >= .99)), 4)}
    if rms < .0001 and peak < .001:
        return PreparedAudio(audio, metrics, "no_audio_input")
    # Trim long button-press silence, keeping 150 ms around active frames.
    frame = max(1, rate // 50)
    starts = np.arange(0, len(samples), frame)
    levels = np.array([np.sqrt(np.mean(samples[i:i + frame] ** 2)) for i in starts])
    active = np.flatnonzero(levels >= max(.0002, float(levels.max()) * .04))
    if not len(active):
        return PreparedAudio(audio, metrics, "no_audio_input")
    start = max(0, int(starts[active[0]]) - int(rate * .15))
    end = min(len(samples), int(starts[active[-1]]) + frame + int(rate * .15))
    samples = samples[start:end]
    # Bounded gain helps quiet laptop microphones without amplifying silence.
    gain = min(8.0, .9 / peak)
    samples *= gain
    count = max(1, round(len(samples) * 16000 / rate))
    converted = np.interp(np.arange(count) * rate / 16000, np.arange(len(samples)), samples)
    pcm = np.rint(np.clip(converted, -1, 1) * 32767).astype("<i2")
    stream = io.BytesIO()
    with wave.open(stream, "wb") as target:
        target.setnchannels(1); target.setsampwidth(2); target.setframerate(16000)
        target.writeframes(pcm.tobytes())
    return PreparedAudio(stream.getvalue(), {**metrics,"normalization_gain":round(gain, 2)})
