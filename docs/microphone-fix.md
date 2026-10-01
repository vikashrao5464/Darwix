# Microphone recognition fix

The user reported that Chrome had microphone permission and the assistant spoke, but every spoken reply was rejected. After input capture improvements, the meter moved and recognition worked, but the user reported poor accuracy. The default recognizer is now local Whisper `small.en`. The user retried an amount on Chrome with the laptop microphone and confirmed that the transcript and assistant confirmation matched. This is one user-reported check; no human recording or accent benchmark was collected.

## Behavior

- Resume the browser audio context before capture; show a microphone selector and a live input meter. Enable laptop echo/noise reduction, with automatic microphone gain disabled.
- Reject nearly silent input with a microphone-specific explanation. Trim button-press silence, mix to mono, apply bounded gain and convert to 16-kHz PCM before recognition.
- Run local Whisper with CPU int8 inference, speech activity detection and rejection of segments with high no-speech probability or repetitive output. The API uses prepared local model files and never downloads a model during a call.
- Bound recognition with a 30-second timeout and kill/reap the worker on timeout or cancellation. Missing models and provider errors safely fall back to typing.
- Show uncertain transcriptions as editable review text. They do not update qualification until explicitly submitted. Accepted spoken details still require confirmation before they become confirmed qualification values.
- Retain the legacy Windows ASR adapter through configuration; keep Windows SAPI for speech output. No audio is sent to a hosted service by the default ASR adapter.

The legacy Windows confidence threshold (0.55) and Whisper decoder evidence threshold (0.37) use different scales. Neither is a calibrated accuracy percentage. Model revisions and tested dependencies are pinned; PyAV 16.1.0 is used with faster-whisper 1.2.1.

## Verification

| Check | Observed result | Evidence |
|---|---|---|
| Backend regression suite | 108 passed; one upstream deprecation warning | [JUnit](../evaluations/voice/microphone-fix-tests.xml) |
| Frontend production build | Passed | `npm --prefix frontend run build` |
| Dependency consistency | Passed | `.venv/Scripts/python.exe -m pip check` |
| Actual speech endpoint | 4/4 passed: consent, quiet consent, quiet grounded FAQ, amount requiring confirmation | [JSON](../evaluations/voice/microphone-fix.json) |
| Chrome call flow | Actual captured synthetic microphone audio reached a cited answer; unsupported FAQ fallback, spoken output, mock escalation and consented downloadable WAV passed; no page errors | [JSON](../evaluations/voice/browser-smoke.json) |
| Local model setup | `small.en` ready at the configured ignored model path | `scripts/setup_asr.py` |
| Human laptop microphone | User confirmed spoken amount matched transcript/confirmation | User report in this session |

Tests deliberately cover silent input without an ASR call, quiet stereo audio, gain/clipping bounds, uncertain transcript redaction without state changes, separate provider thresholds, missing model, noisy/repetitive segment filtering, and worker timeout/cancellation cleanup.

The [model comparison](../evaluations/voice/asr-model-comparison.json) measured four short synthesized inputs per model. `base.en` recognized these examples in 1,664–1,787 ms; `small.en` took 3,766–3,977 ms including worker startup and inference. Both produced correct text on these four samples. The user reported improvement after switching to `small.en`; the synthetic comparison alone does not establish improved human accuracy. Actual speech HTTP requests took 3,964–8,318 ms, including additional controller/retrieval work where applicable. These are measured probe durations, not Q4 latency measurements or a production service benchmark.

## Files changed for this fix

| Area | Files |
|---|---|
| New local ASR implementation | `backend/app/providers/whisper_asr.py`, `backend/app/providers/whisper_worker.py`, `backend/app/voice/audio.py` |
| Provider wiring, audio endpoint and diagnostics | `backend/app/providers/asr.py`, `backend/app/main.py`, `backend/app/config.py`, `backend/app/api/speech.py`, `backend/app/logging_config.py` |
| Dependencies | `backend/requirements.txt`, `backend/requirements-lock.txt` |
| Backend tests | `backend/tests/test_audio.py` (new), `backend/tests/conftest.py`, `backend/tests/test_voice.py` |
| Browser capture, microphone controls and review | `frontend/src/lib/voice.js`, `frontend/src/pages/CallDemo.jsx`, `frontend/src/style.css` |
| Browser verification | `frontend/tests/call-smoke.mjs`, `evaluations/voice/browser-smoke.json` |
| Setup and reproducible probes | `scripts/setup_asr.py` (new), `scripts/evaluate_microphone.py` (new), `scripts/evaluate_voice.py` |
| New verification evidence | `evaluations/voice/microphone-fix-tests.xml`, `evaluations/voice/microphone-fix.json`, `evaluations/voice/asr-model-comparison.json` |
| Configuration and documentation | `.env.example`, `README.md`, `docs/architecture.md`, `docs/q1-results.md`, `docs/microphone-fix.md` (new) |

The ignored local `.env` was updated for Whisper `small.en` and its 30-second timeout. Model files, SQLite state, captured diagnostic audio, private consented recordings and screenshots remain ignored. Credentials are not part of the change inventory.

## Commands and manual steps

From the repository root in PowerShell, install the tested dependencies and prepare the public model once:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
.\.venv\Scripts\python.exe scripts/setup_asr.py
```

For an existing `.env`, set `ASR_PROVIDER=whisper`, `WHISPER_MODEL_NAME=small.en`, `WHISPER_MODEL_DIR=data/state/models/whisper-small.en` and `ASR_TIMEOUT_SECONDS=30`. Fresh installations can copy `.env.example` as described in the [README](../README.md). The model download needs internet access once; subsequent recognition uses local files only. No ASR API key is required.

Start Qdrant and run the backend and frontend in separate terminals:

```powershell
docker compose up -d qdrant
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
```

```powershell
npm --prefix frontend run dev
```

Reproduce the relevant checks with the services running and the existing synthetic WAV fixtures available:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=evaluations/voice/microphone-fix-tests.xml
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts/evaluate_microphone.py
npm --prefix frontend run test:call
```

**Manual intervention:** allow microphone access, select the laptop input if needed, and check that the meter moves while speaking. Review/correct uncertain transcripts and confirm qualification values. The backend has already been restarted with this model in the current workspace; refresh `/call` and start a new call when picking up the updated browser UI. Windows desktop voices are still required for the current TTS adapter. Real callbacks/escalations require a human because this prototype only stores mock requests.

Remaining limitations: English-only recognition in this phase, a CPU inference delay of several seconds on this machine, no measured human accent/noise accuracy, and no streaming recognition. Localization and real-time insights remain deferred to later phases. The recognition improvement does not change the synthetic business-policy assumptions or the deterministic qualification rules.
