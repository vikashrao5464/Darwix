import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from app.config import ROOT


class MMSTTSProvider:
    """Local native-language models in timeout-bounded workers; no hosted text."""
    def __init__(self, settings, english):
        self.settings, self.english = settings, english
        self.slots = asyncio.Semaphore(1)

    async def synthesize(self, text, language='en'):
        if language == 'en':
            return await self.english.synthesize(text, 'en')
        name = {'fil': 'tgl', 'fil-en': 'tgl', 'id': 'ind'}.get(language)
        if not name:
            raise ValueError('unsupported_tts_language')
        model = self.settings.localization_tts_model_dir / name
        if not model.is_absolute():
            model = ROOT / model
        if not (model / 'config.json').is_file():
            raise RuntimeError('local_tts_model_missing_run_setup_localization')
        async with self.slots:
            with tempfile.TemporaryDirectory(prefix='darwix-mms-') as directory:
                source, output = Path(directory) / 'text.txt', Path(directory) / 'speech.wav'
                source.write_text(text, encoding='utf-8')
                process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'app.providers.mms_worker',
                    '--model', str(model), '--input', str(source), '--output', str(output),
                    cwd=str(ROOT / 'backend'), stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                try:
                    await asyncio.wait_for(process.wait(), self.settings.localization_tts_timeout_seconds)
                except BaseException:
                    if process.returncode is None:
                        process.kill()
                        await process.wait()
                    raise
                if process.returncode or not output.is_file():
                    raise RuntimeError('local_tts_worker_failed')
                return output.read_bytes()
