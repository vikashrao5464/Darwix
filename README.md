# Darwix AI Engineer Assessment

Implemented scope: **Phases 0, 1 and 2** of [BUILD_STEPS.md](BUILD_STEPS.md). This repository provides a running FastAPI/React prototype and a traceable Q2 knowledge base connected to the Q1 business-loan voice agent.

**All business documents and rules are synthetic demonstration content. They are not Darwix policies or an actual lender's offer.** No official business dataset was supplied. The default demo runs without hosted-provider credentials.

The demo extracts PDF, HTML, Markdown, text, JSON and CSV; cleans boilerplate; redacts basic PII; deduplicates; chunks with citations; indexes vectors in Qdrant; and returns grounded excerpts or a human-assistance fallback. SQLite stores calls, qualification state, redacted transcripts and mock leads/callbacks/escalations alongside the Phase 0 tables.

Local entry points after startup:

- [Voice call and knowledge demo](http://127.0.0.1:5173/call)
- [API documentation](http://127.0.0.1:8000/docs)
- [Health](http://127.0.0.1:8000/health)
- [Qdrant dashboard](http://127.0.0.1:6333/dashboard)

`/live` is a clearly marked placeholder. Q3 localization and Q4 streaming/nudges/component-latency metrics belong to later phases and are not implemented.

The default embedding adapter uses deterministic feature hashing with weighted headings, **not a trained semantic embedding model**. The default answer adapter returns verbatim evidence, **not generative LLM output**. Optional OpenAI adapters support semantic embeddings and LLM evidence selection; they are covered by mocked tests but have not been verified against a live account. Source content must still answer the question regardless of provider choice.

See [architecture](docs/architecture.md), [knowledge-base behavior](docs/knowledge-base.md), [actual retrieval evaluation](docs/q2-retrieval-evaluation.md), [manual chunk inspection](docs/chunk-review.md), and [verification evidence](docs/phase-0-1-verification.md).

## Q1 voice behavior and evidence

Open `/call`, start a demo call, consent, then use **Speak a reply** / **Send voice reply** or type a response. The backend uses local Whisper `small.en` recognition and Microsoft David Desktop spoken output. Choose your microphone and watch the input meter while listening. Laptop noise reduction is enabled; automatic microphone gain is disabled to avoid clipping. Quiet audio receives bounded gain and is converted to mono 16-kHz PCM before recognition. It collects one field at a time, requests confirmation for newly recognized spoken details, confirms tentative/conflicting values, queries the existing KB for FAQs/objections and produces source-backed **preliminary** eligibility. Six HTTP tools are available under `/api/voice/tools/`; Swagger documents their strict schemas.

Recordings require both the recording checkbox and qualification consent. The browser mixes microphone and spoken agent audio after consent, caps capture at five minutes and saves on completion/end/escalation. Raw recordings are private, ignored files under `data/audio/private`; stored transcripts redact basic PII. Use synthetic details. Closing/reloading the page discards unsaved audio; recovery/reconnection is not implemented.

[Q1 observed results](docs/q1-results.md) contain **three synthesized scripted call recordings**, transcripts and actual checks covering scenarios A-E. The original Windows ASR baseline reached the intended behavior on **5/6** separate WAV probes; the amount phrase was withheld below its 0.55 confidence threshold. The current Whisper adapter passes the four checks in the [microphone regression report](evaluations/voice/microphone-fix.json), including that amount. These fixtures do not replace human microphone testing. [Phase 2 changed files](docs/phase-2-files.md) and [verification](docs/phase-2-verification.md) document the implemented scope.

Uncertain transcriptions appear in a review box; no qualification value changes until you explicitly use the reviewed text. Silent input produces a microphone-specific message instead of the generic recognition error. The [microphone fix report](docs/microphone-fix.md) includes actual tests, model comparison and the user-confirmed spoken-amount check.

The local interpreter handles explicit single-field English replies and number words. Optional hosted interpretation classifies intent/exact evidence; deterministic validation and state transitions still control business actions. Missing evidence, stale rules and provider timeouts produce fallbacks. Leads, callbacks and human requests are **mock local records**; a coordinator must take any real action.

## Results

The synthetic manifest produces 23 chunks from eight sources. One exact duplicate is skipped and one near duplicate is flagged and retained. Eleven retrieval cases cover product, policy, qualification, FAQ, objection, unavailable content, metadata filters and paraphrases. Actual output: **10 correct, 1 incorrect**. The failed paperwork paraphrase safely falls back; the local vectors do not understand that synonym. The [JSON report](evaluations/retrieval/results.json) includes every returned record, source, score, citation and verdict.

Tests cover extraction failure, PII and ordinary business numbers, deduplication, chunk provenance, SQLite insertion/readback, metadata filters, unsupported questions, timeouts, invalid LLM quotes, failed index writes, rebuild preservation and version replacement. Test-only latency rows use synthetic numbers to check persistence; they are not call latency measurements.

## Setup (PowerShell, repository root)

Prerequisites: Python 3.12+; Node 20.19+ or 22.12+; Docker Desktop running for the default Qdrant configuration; Windows PowerShell 5.1 and David/Zira desktop voices for spoken output; the English desktop recognizer is needed only if selecting the legacy Windows ASR adapter. Download the default local Whisper model once with `scripts/setup_asr.py`. Cross-platform text/KB operation remains available; Windows speech errors fall back to typed replies. Verified here on Python 3.14.3 and Node 22.20.0. The tested dependencies are pinned in `backend/requirements-lock.txt` and `frontend/package-lock.json`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d qdrant
npm --prefix frontend ci
.\.venv\Scripts\python.exe scripts/setup_asr.py
.\.venv\Scripts\python.exe scripts/ingest.py --rebuild
powershell.exe -NoProfile -NonInteractive -File scripts/check_speech.ps1
```

Run the backend in one terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
```

Run the frontend in another:

```powershell
npm --prefix frontend run dev
```

Check the API and ask a supported or unsupported question:

```powershell
curl.exe http://127.0.0.1:8000/health
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/knowledge/answer -Method Post -ContentType 'application/json' -Body '{"query":"What is the processing fee?","product":"business_loan"}'
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/knowledge/answer -Method Post -ContentType 'application/json' -Body '{"query":"What cashback applies to lunar tourism?","product":"business_loan"}'
```

Use the explicit loopback addresses above: this machine has another listener on `localhost:8000` via IPv6. If either port is occupied on another machine, select a free backend/frontend port and update `VITE_API_BASE_URL`/`CORS_ORIGINS` in `.env`. Restart Vite after environment changes.

Without Docker, set `QDRANT_URL=` in `.env` to use Qdrant's embedded persistent mode. **Stop the backend before running ingestion/evaluation CLI commands in this mode**, because only one process can open the local store. While the backend is running, ingestion through the HTTP API uses its existing client. Tests use isolated in-memory Qdrant and need neither Docker nor keys.

On macOS/Linux replace `.\.venv\Scripts\python.exe` with `.venv/bin/python` and copy the environment file with `cp .env.example .env`. The pinned Windows environment was tested here; other OS/Python combinations have not been exercised.

## Verification commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=evaluations/phase-2-tests.xml
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts/evaluate_retrieval.py
.\.venv\Scripts\python.exe scripts/evaluate_voice.py
npm --prefix frontend run test:call
.\.venv\Scripts\python.exe scripts/evaluate_microphone.py
```

The evaluator writes `evaluations/retrieval/results.json` and `docs/q2-retrieval-evaluation.md`. **It exits 1 when any case is incomplete/incorrect**, including the documented local paraphrase miss; this is an honest evaluation result, not a script crash. A clean index must be ingested first.

The voice evaluator requires a running backend and ingested KB. It writes three public **synthetic** WAV fixtures plus detailed JSON/transcripts and `docs/q1-results.md`. `--without-audio` runs controller-only checks on machines without Windows speech and marks audio evidence absent. The Chrome test requires the running frontend/backend, generated `probe_browser_faq.wav` and Chrome; set `CHROME_PATH` if installed elsewhere. It uses synthetic fake-microphone audio and saves a verification JSON.

PDF fixtures are already included. To regenerate them:

```powershell
.\.venv\Scripts\python.exe scripts/create_fixtures.py
```

`--rebuild` replaces only the configured provider's knowledge collection. It prepares and validates a new collection before switching the active Qdrant alias. Failed extraction in a full rebuild aborts the switch; failed embeddings or staging writes preserve the prior active index. The command never deletes SQLite rows or another provider's namespace. Run a single ingestion writer at a time.

## Environment variables

All configuration is documented in [.env.example](.env.example). Secrets are optional for the local demo:

| Variable | Default / purpose |
|---|---|
| `APP_ENV`, `LOG_LEVEL` | Environment label and JSON application log level |
| `CORS_ORIGINS` | JSON list of permitted frontend origins |
| `DATABASE_URL` | SQLite relational state in `data/state/darwix.db` |
| `QDRANT_URL`, `QDRANT_PATH`, `QDRANT_COLLECTION` | Remote service, embedded location, namespace prefix |
| `QDRANT_API_KEY` | Optional secret for secured remote Qdrant |
| `EMBEDDING_PROVIDER` | `hash` or `openai` |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` | Hosted model name and vector dimension; hash default is 512 |
| `LLM_PROVIDER`, `LLM_MODEL` | `extractive` or `openai`, and hosted model name |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL` | Hosted-provider secret and API endpoint |
| `PROVIDER_TIMEOUT_SECONDS` | Timeout for provider and retrieval operations; no automatic retries |
| `RETRIEVAL_MIN_SCORE` | Cosine evidence threshold, 0.3 for the fixture baseline |
| `NEAR_DUPLICATE_THRESHOLD` | Token Jaccard threshold, 0.88 |
| `CHUNK_WORDS`, `CHUNK_OVERLAP_WORDS` | 400-word bound, 60-word overlap within long sections |
| `TERMINOLOGY_PATH` | JSON terminology normalization map |
| `GOVERNMENT_ID_PATTERNS` | JSON list of regex redaction patterns |
| `VITE_API_BASE_URL` | Browser-accessible backend URL |
| `QUALIFICATION_RULES_PATH` | Reviewed synthetic rules with source ID/version/checksum/quote |
| `ASR_PROVIDER`, `ASR_LANGUAGE` | `whisper` local English by default; `windows` enables legacy `en-US` dictation |
| `TTS_PROVIDER`, `TTS_VOICE` | `windows`, Microsoft David Desktop |
| `VOICE_ASR_MIN_CONFIDENCE` | 0.55 for legacy Windows confidence; below threshold requires review/repetition |
| `WHISPER_MODEL_NAME`, `WHISPER_MODEL_DIR` | `small.en`, ignored local model directory; `base.en` is a smaller alternative |
| `WHISPER_CPU_THREADS`, `ASR_TIMEOUT_SECONDS`, `WHISPER_MIN_SCORE` | 2 threads, 30-second timeout, 0.37 decoder evidence threshold |
| `VOICE_MAX_TURNS`, `VOICE_AUDIO_MAX_SECONDS` | 60 turns per call, 20 seconds per uploaded utterance (UI stops at 18) |
| `RECORDINGS_DIR` | Private, ignored consented audio directory |

To exercise hosted providers, manually supply a valid account key and choose `openai` for one or both adapters. Rebuild after changing embeddings, dimensions or terminology, rerun the evaluation, and recalibrate the confidence threshold for that model. Provider signatures isolate embedding spaces to prevent mixing incompatible vectors. The example model names are configuration examples, not a performance claim. The adapter follows the [official embeddings API](https://developers.openai.com/api/reference/resources/embeddings/methods/create) and [Structured Outputs contract](https://developers.openai.com/api/docs/guides/structured-outputs).

## Manual intervention and current limits

- Start Docker Desktop and the application processes; open the browser demo. Allow microphone access, use a headset, and validate a human spoken call and recording. No keys are required for the default mode.
- A key was found in `.env.example` during this work. The template is now blank and the value was moved into ignored `.env`. **Rotate the exposed key before using hosted providers.**
- Before using real business material, obtain approved sources, mark `synthetic: false` only when justified, update the manifest, review extraction/redaction/chunks, and rebuild. Do not put customer documents in this demo repository.
- A live hosted-provider run requires your account key, access to the configured models and possible usage charges. No hosted calls were made during this implementation.
- Human escalation/callbacks write local mock requests and never contact a person. Exact dates, availability and real appointment coordination require a human.
- Local Whisper `small.en` replaces the weak Windows dictation baseline for recognition; Windows SAPI remains the TTS adapter. The user verified a spoken amount on Chrome with a laptop mic. This single check is not an accent/accuracy benchmark. Use a headset in noisy surroundings, review uncertain transcripts, and confirm recognized fields. No localization or streaming voice is claimed.
- Model setup needs internet access to download the public pinned model revision once; recognition subsequently uses local files only and sends no audio to a hosted service. Install the pinned dependency lock: the tested PyAV version is compatible with faster-whisper 1.2.1.
- The Windows 0.55 confidence and Whisper 0.37 decoder evidence thresholds use different scales. Neither is a calibrated accuracy percentage.
- Qualification rules are reviewed configuration, not automatic policy extraction. Changes to policy sources/version/checksum/record IDs require manual rule review; stale evidence blocks eligibility.
- PDF extraction requires a text layer; scanned PDFs need OCR. PDF heading recognition uses explicit heading markers in the fixture; ordinary PDF typography is kept page-by-page. Ambiguous dates use the documented day-first convention.
- Regex PII detection is a baseline, not a complete privacy control. Amounts are preserved when clearly identified as currency/turnover. Phone-like unlabeled numbers are conservatively redacted. Source metadata must also be reviewed before real ingestion.
- Near duplicates are retained to avoid erasing conflicting amounts or rules. This phase reports similarity; it does not reconcile contradictions. The manual source review is required before using real policy data.
- The public prototype API has no authentication. Keep it on loopback. Production needs access control, approved retention, encryption, audited source/version management, provider quality testing and proper schema migrations.
- Snapshot index replacement is suitable for a small corpus and a single ingestion writer. Multiple API workers/CLI writers need distributed coordination; large corpora need batch indexing and production rollout procedures.

The broader assessment remains incomplete until Phases 3 through 7 provide the localization, real-time and submission evidence described in the supplied instructions.
