"""One warm cancellable Whisper worker per stream; bounded chunks, no full-call input."""
import asyncio
import base64
import json
import os
import subprocess
import sys
from app.config import ROOT
from app.schemas.voice import ASRResult

class LocalStreamingASR:
    def __init__(self, settings, language='en'):
        self.settings, self.language, self.process = settings, language, None
        self.results = asyncio.Queue(maxsize=2)
    async def open_stream(self):
        model = self.settings.whisper_model_dir
        if not model.is_absolute(): model = ROOT / model
        if not (model / 'model.bin').is_file(): raise RuntimeError('local_stream_model_missing')
        self.process = await asyncio.create_subprocess_exec(sys.executable, '-m', 'app.providers.stream_worker',
            '--model',str(model),'--language',self.language,'--threads',str(self.settings.whisper_cpu_threads),
            cwd=str(ROOT/'backend'),stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=65536,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            line = await asyncio.wait_for(self.process.stdout.readline(), self.settings.asr_timeout_seconds)
            if json.loads(line) != {'ready':True}: raise RuntimeError('stream_start_failed')
        except BaseException:
            await self.close(); raise
    async def send_audio(self, chunk):
        try:
            self.process.stdin.write(json.dumps({'audio':base64.b64encode(chunk).decode('ascii')}).encode()+b'\n')
            await self.process.stdin.drain()
            line = await asyncio.wait_for(self.process.stdout.readline(), self.settings.asr_timeout_seconds)
            await self.results.put(ASRResult.model_validate(json.loads(line)))
        except BaseException:
            await self.close(); raise
    async def receive_events(self):
        yield await self.results.get()
    async def close(self):
        if self.process and self.process.returncode is None:
            self.process.kill()
            await self.process.wait()
