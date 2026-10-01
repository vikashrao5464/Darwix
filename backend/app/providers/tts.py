from typing import Protocol


class TTSProvider(Protocol):
    """Speech synthesis adapter, returning PCM WAV bytes."""
    async def synthesize(self, text: str, language: str) -> bytes: ...
