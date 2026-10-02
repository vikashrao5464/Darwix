from typing import AsyncIterator, Protocol


class ASRProvider(Protocol):
    """Utterance recognition for interactive calls."""
    async def transcribe(self, audio: bytes): ...


def create_asr_provider(settings):
    if settings.asr_provider == "whisper":
        from app.providers.whisper_asr import WhisperASRProvider
        return WhisperASRProvider(settings)
    from app.providers.windows_speech import WindowsSpeechProvider
    return WindowsSpeechProvider(settings)


class StreamingASRProvider(Protocol):
    """Continuous fixed-chunk stream implemented by LocalStreamingASR."""
    async def open_stream(self) -> None: ...
    async def send_audio(self, chunk: bytes) -> None: ...
    def receive_events(self) -> AsyncIterator[dict]: ...
