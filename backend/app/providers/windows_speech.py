import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path

from app.config import ROOT
from app.schemas.voice import ASRResult


class WindowsSpeechProvider:
    """Offline Windows SAPI provider. No customer text enters shell commands."""
    def __init__(self, settings):
        self.settings = settings
        self.slots = asyncio.Semaphore(2)

    async def _run(self, action, source, output):
        if os.name != "nt":
            raise RuntimeError("windows_speech_unavailable_on_this_platform")
        process = await asyncio.create_subprocess_exec(
            "powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
            "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/windows_speech.ps1"),
            "-Action", action, "-InputPath", str(source), "-OutputPath", str(output),
            "-Voice", self.settings.tts_voice, "-Language", self.settings.asr_language,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            await asyncio.wait_for(process.wait(), self.settings.provider_timeout_seconds)
        except BaseException:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        if process.returncode or not output.exists():
            raise RuntimeError("windows_speech_provider_failed")

    async def synthesize(self, text, language="en"):
        if language != "en":
            raise ValueError("unsupported_language")
        async with self.slots:
            with tempfile.TemporaryDirectory(prefix="darwix-tts-") as directory:
                source, output = Path(directory) / "input.txt", Path(directory) / "output.wav"
                source.write_text(text, encoding="utf-8")
                await self._run("synthesize", source, output)
                return output.read_bytes()

    async def transcribe(self, audio):
        async with self.slots:
            with tempfile.TemporaryDirectory(prefix="darwix-asr-") as directory:
                source, output = Path(directory) / "input.wav", Path(directory) / "output.json"
                source.write_bytes(audio)
                await self._run("transcribe", source, output)
                return ASRResult.model_validate(json.loads(output.read_text(encoding="utf-8-sig")))
