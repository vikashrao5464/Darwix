import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.config import ROOT
from app.schemas.voice import ASRResult


class WhisperASRProvider:
    """Local CPU recognition in a cancellable process; models are prepared offline."""
    def __init__(self, settings):
        self.settings = settings
        self.slots = asyncio.Semaphore(1)

    async def transcribe(self, audio, language="en"):
        model = self.settings.whisper_model_dir
        if not model.is_absolute():
            model = ROOT / model
        if not (model / "model.bin").is_file():
            raise RuntimeError("local_asr_model_missing_run_setup_asr")
        async with self.slots:
            with tempfile.TemporaryDirectory(prefix="darwix-whisper-") as directory:
                source, output = Path(directory) / "input.wav", Path(directory) / "result.json"
                source.write_bytes(audio)
                process = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "app.providers.whisper_worker",
                    "--model", str(model), "--input", str(source), "--output", str(output),
                    "--threads", str(self.settings.whisper_cpu_threads),
                    "--language", language or "auto",
                    cwd=str(ROOT / "backend"),
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                try:
                    await asyncio.wait_for(process.wait(), self.settings.asr_timeout_seconds)
                except BaseException:
                    if process.returncode is None:
                        process.kill()
                        await process.wait()
                    raise
                if process.returncode or not output.is_file():
                    raise RuntimeError("local_asr_failed")
                return ASRResult.model_validate(json.loads(output.read_text(encoding="utf-8")))
