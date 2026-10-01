from typing import AsyncIterator, Protocol


class ASRProvider(Protocol):
    """Utterance ASR in Phase 2; streaming is a separate Phase 4 contract."""
    async def transcribe(self, audio: bytes): ...


def create_asr_provider(settings):
    if settings.asr_provider == "whisper":
        from app.providers.whisper_asr import WhisperASRProvider
        return WhisperASRProvider(settings)
    from app.providers.windows_speech import WindowsSpeechProvider
    return WindowsSpeechProvider(settings)


class StreamingASRProvider(Protocol):
    """Contract reserved for the streaming implementation in Phase 4."""
    async def open_stream(self) -> None: ...
    async def send_audio(self, chunk: bytes) -> None: ...
    def receive_events(self) -> AsyncIterator[dict]: ...
