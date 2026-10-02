# Darwix AI Engineer Assessment

This repository implements the **Phases 0–7 prototype** in [BUILD_STEPS.md](BUILD_STEPS.md): a knowledge-grounded voice agent, traceable knowledge base, Philippine/Indonesian reminders and real-time call insights. It runs as one FastAPI backend and a small React application.

**Business content, account amounts and public call dialogues are synthetic demonstration material, not Darwix policies.** No official business dataset was supplied. Human/native-speaker and compliance validation remain manual requirements. Defaults use local speech, deterministic evidence selection and rules; hosted AI credentials are optional.

## Demo links

- [Call and knowledge demo](http://127.0.0.1:5173/call): Q1 qualification or Q3 localized reminders.
- [Live dashboard](http://127.0.0.1:5173/live): select the stress recording and start replay.
- [Recorded screen demo](evaluations/realtime/live-demo.webm): supported FAQ, unsupported fallback and actual streaming nudges/suppression.
- [API docs](http://127.0.0.1:8000/docs), [health](http://127.0.0.1:8000/health).
- [Final checklist](docs/submission-checklist.md): implemented evidence and remaining manual validation.

Local links require setup below. The video is a silent automated Chrome screen recording; listen to the linked WAV calls for speech. It is not a native-speaker listening assessment.

## Architecture

[Mermaid and design decisions](docs/architecture.md) describe shared voice/KB tools, SQLite state, Qdrant snapshots and streaming analysis. Microphone audio goes through provider adapters and deterministic call state. Business answers retrieve first and cite validated evidence. Q4 independently reads timed chunks into warm Whisper, bounded rolling context, detection, suppression and WebSocket delivery.

Feature-hash vectors are a lexical baseline; the default answer adapter selects verbatim evidence. Optional semantic embeddings, interpretation and Q4 classification use the existing OpenAI adapter and mocked contract tests. Live hosted AI behavior has not been measured.

## Q1: business-loan qualification

Open /call, select business loans, start, consent, and speak or type. Local Whisper small.en recognizes speech; Windows David speaks replies. Select the microphone and watch the meter. Browser noise suppression and bounded normalization help quiet input. Uncertain text is reviewed before use; newly spoken values require confirmation. Silence returns a microphone-specific message.

Shared tools collect deterministic fields, preserve tentative/conflicting values, retrieve FAQs/objections and evaluate source-backed **preliminary** eligibility. Leads, callbacks and escalations are mock records. A human coordinates actual contact; no credit approval is performed.

[Three synthesized scripted calls and executed checks](docs/q1-results.md) cover cooperation, objection, conflicting/incomplete details, unsupported questions and human assistance. [The microphone fix](docs/microphone-fix.md) records the English comparison and user-confirmed spoken amount. [Chrome regression](evaluations/voice/browser-smoke.json) uses actual ASR/TTS and synthetic microphone input.

Browser recordings require separate recording and conversation consent. Private audio is ignored under data/audio/private, capped at five minutes and saved on completion/end/escalation. Reloading discards unsaved audio. Stored transcripts redact basic PII.

## Q2: production-minded knowledge base

Fourteen sources yield 68 traceable chunks: 23 Q1 and 45 Q3 chunks. PDF, HTML, Markdown, text, JSON and CSV pass through extraction, deterministic cleaning, PII redaction, dedupe, normalization and heading/page-aware chunking. One exact duplicate is skipped; a near duplicate remains flagged for review.

Chunks retain source/type/page/section/version/checksum/record ID. Retrieval applies product/language filters and top-k ranking. Remote Qdrant receives keyword indexes for strict-mode filtering. Provider signatures isolate vector spaces. Rebuild validates staging before an atomic alias switch; failed extraction, embeddings, metadata indexing or writes preserve the active index.

[KB specification](docs/knowledge-base.md), [chunk review](docs/chunk-review.md) and [eleven actual retrieval cases](docs/q2-retrieval-evaluation.md) document **10 correct, one safe paraphrase miss**. The lexical baseline misses “paperwork” as a synonym. Unsupported/insufficient evidence never becomes an invented policy answer.

## Q3: localized reminders

Philippines: life-insurance premium/renewal reminders in English, Filipino/Tagalog and Taglish. Indonesia: installments in formal, colloquial and finance-mixed Bahasa. Choose a starting register in /call; short acknowledgements preserve it. For an ambiguous spoken switch, first send a typed reply with the response-language selector. Interface labels remain English; agent replies/fallbacks follow register.

Local multilingual Whisper medium handles recognition, Meta MMS tgl/ind handles native speech, and Windows David handles English. Greetings, objections, money/date wording and confirmations are explicit draft localization; business facts come from filtered KB evidence. Payment statements and spoken callback times require confirmation. No payment is verified, fee waived or policy renewed.

[Q3 observations](docs/q3-localization-report.md) include two synthesized scripted calls per market, three phrasing examples per market, six actual ASR probes and one publisher-labeled Batak human sample. **Four of six synthetic probes reached intended behavior; two short Filipino/Taglish probes returned fallbacks.** One clean news sample does not establish accent robustness or finance-call accuracy.

MMS licenses assume noncommercial assessment use. Corpus audio is downloaded privately rather than redistributed. Native speakers must review phrasing, pronunciation/prosody and consented human calls.

## Q4: real-time insights and nudges

Open /live and start replay. The original Q1 cooperative recording is a negative control; the 66-second Q1 stress recording combines its actual opening with explicitly injected synthetic opportunity, risky-agent, frustration, payment/callback, noise and duplicate windows.

The server reads six-second chunks at real-time speed, continuously recognizes final chunk text and emits events while replay is active. It never transcribes the entire recording upfront. Whisper stays warm; context, backlog and subscribers are bounded. One active replay is admitted. ASR failure/overload stops safely.

Signals provide confidence-scored, evidence-backed guidance with configurable threshold, per-type cooldown, normalized evidence/action fingerprints, priority and expiry. Weak evidence is withheld and repeated issues do not spam nudges. Speaker labels use registered synthetic role/timing annotations; mixed-role/unknown chunks stay unknown. Diarization and token-level partial transcription remain unimplemented.

[Actual quality and generated latency](docs/q4-latency-report.md) include CLI/rendered Chrome runs, per-window expected/emitted signals, FP/FN, suppression and persisted acknowledged samples. Capture delay (up to six seconds) and model warmup are separate from pipeline latency. Delivery includes the acknowledgement return trip. The llm_latency_ms field measures deterministic nudge construction by default; optional semantic classification belongs to signal time.

## Results and evidence

| Area | Evidence |
|---|---|
| Q1 voice agent | [Three calls, transcripts and checks](docs/q1-results.md) |
| Q1 grounding | [Executed tool logs/citations](evaluations/voice/results.json), [Chrome check](evaluations/voice/browser-smoke.json) |
| Q2 retrieval | [Eleven evaluated queries and safe miss](docs/q2-retrieval-evaluation.md) |
| Q3 Philippines | [Two calls and localization examples](docs/q3-localization-report.md) |
| Q3 Indonesia | [Two calls and accent observations](docs/q3-localization-report.md) |
| Q4 real-time | [Chrome video](evaluations/realtime/live-demo.webm), [events](evaluations/realtime/browser-smoke.json) |
| Q4 latency | [Generated P50/P95](docs/q4-latency-report.md), [samples](evaluations/realtime/latency.json) |
| Q4 quality | [FP/FN and suppression](evaluations/realtime/results.json) |
| Automated checks | [Final JUnit](evaluations/final-tests.xml), [handoff](docs/remaining-phases-verification.md) |

Reports retain actual errors. Synthetic fixtures and mocked contracts do not certify human accuracy, production scale or compliance.

## Setup (PowerShell, repository root)

Tested on Python 3.14.3 and Node 22.20.0. Use Python 3.12+, Node 20.19+ or 22.12+, Docker Desktop for default Qdrant, and Windows PowerShell with David/Zira voices for English TTS/fixture generation. Recognition downloads pinned models once, then runs offline. Other operating systems have not been exercised.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d qdrant
npm --prefix frontend ci
.\.venv\Scripts\python.exe scripts/setup_asr.py
.\.venv\Scripts\python.exe scripts/setup_localization.py
.\.venv\Scripts\python.exe scripts/setup_accent_sample.py
.\.venv\Scripts\python.exe scripts/ingest.py --rebuild
powershell.exe -NoProfile -NonInteractive -File scripts/check_speech.ps1
```

The checked-in recordings/catalogue are ready to replay. Regenerate the Q4 fixture with scripts/create_realtime_fixtures.py if needed, and rerun it after regenerating Q1 audio to refresh replay metadata. The regional sample stays ignored and requires its setup script.

Backend terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
```

Frontend terminal:

```powershell
npm --prefix frontend run dev
```

Use explicit loopback URLs. For other ports, change VITE_API_BASE_URL/CORS_ORIGINS and restart Vite. QDRANT_URL= selects embedded Qdrant without Docker; stop the backend before CLI ingestion/evaluation because only one process may open that store. Tests use isolated in-memory Qdrant. Do not overwrite an existing .env when adding defaults.

Verification (services running for browser/replay checks):

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=evaluations/final-tests.xml
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts/evaluate_retrieval.py
npm --prefix frontend run test:call
npm --prefix frontend run test:localization
.\frontend\node_modules\.bin\playwright.cmd install ffmpeg
.\.venv\Scripts\python.exe scripts/replay_audio.py --file data/audio/q4/q1_insights.wav --output evaluations/realtime/cli-insights.json
.\.venv\Scripts\python.exe scripts/replay_audio.py --file data/audio/q1/cooperative.wav --output evaluations/realtime/cli-cooperative.json
npm --prefix frontend run test:live
.\.venv\Scripts\python.exe scripts/evaluate_realtime.py
.\.venv\Scripts\python.exe scripts/summarize_evidence.py
```

Run replays sequentially: one active replay is allowed. Retrieval evaluation intentionally exits 1 for the documented paraphrase miss; inspect its report. scripts/summarize_latency.py --call-id <id> regenerates selected persisted percentiles. Q4 evaluation selects the observed IDs and distinguishes CLI receipt from rendered Chrome acknowledgement.

Chrome uses its standard Windows path; set CHROME_PATH for another location. Playwright FFmpeg is needed only to regenerate screen video. Full Q1/Q3 reports regenerate with scripts/evaluate_voice.py and scripts/evaluate_localization.py; --without-audio marks absent speech. Browser checks use synthetic microphone input; playback acceleration is disclosed.

## Environment variables

[.env.example](.env.example) documents every default; existing environments use defaults for omitted new values. Credentials are optional in the keyless demo.

| Settings | Purpose |
|---|---|
| APP_ENV, LOG_LEVEL, CORS_ORIGINS, VITE_API_BASE_URL | Environment, redacted logs and browser URLs |
| DATABASE_URL | SQLite state |
| QDRANT_URL, QDRANT_PATH, QDRANT_COLLECTION, QDRANT_API_KEY | Remote/embedded vectors and optional secret |
| EMBEDDING_PROVIDER, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS | Hash default or hosted embeddings |
| LLM_PROVIDER, LLM_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL | Evidence/interpretation and optional hosted configuration |
| PROVIDER_TIMEOUT_SECONDS, RETRIEVAL_MIN_SCORE | Time budget and evidence threshold |
| CHUNK_WORDS, CHUNK_OVERLAP_WORDS, NEAR_DUPLICATE_THRESHOLD | Chunking/dedupe |
| TERMINOLOGY_PATH, GOVERNMENT_ID_PATTERNS, QUALIFICATION_RULES_PATH | Normalization, redaction and reviewed rules |
| ASR_PROVIDER, ASR_LANGUAGE, WHISPER_MODEL_NAME, WHISPER_MODEL_DIR | English small.en default or legacy Windows |
| WHISPER_CPU_THREADS, ASR_TIMEOUT_SECONDS, WHISPER_MIN_SCORE, VOICE_ASR_MIN_CONFIDENCE | CPU bound and distinct decoder/legacy thresholds |
| TTS_PROVIDER, TTS_VOICE | Windows English speech |
| VOICE_MAX_TURNS, VOICE_AUDIO_MAX_SECONDS, RECORDINGS_DIR | Interactive limits/private recordings |
| LOCALIZATION_WHISPER_MODEL_NAME, LOCALIZATION_WHISPER_MODEL_DIR, LOCALIZATION_ASR_TIMEOUT_SECONDS | Multilingual medium (small optional) and timeout |
| LOCALIZATION_TTS_PROVIDER, LOCALIZATION_TTS_MODEL_DIR, LOCALIZATION_TTS_TIMEOUT_SECONDS | Local MMS and synthesis bound |
| REALTIME_CHUNK_SECONDS, REALTIME_WINDOW_SECONDS, REALTIME_QUEUE_SIZE, REALTIME_MAX_SUBSCRIBERS | Six-second capture, 45-second context and bounds |
| REALTIME_MIN_CONFIDENCE, REALTIME_COOLDOWNS, REALTIME_DUPLICATE_SECONDS, REALTIME_NUDGE_EXPIRY_SECONDS | Threshold, cooldown, fingerprints and expiry |
| REALTIME_ACK_TIMEOUT_SECONDS, REALTIME_LLM_ENABLED | Measured delivery eligibility and opt-in classifier |

For hosted AI, supply your account key, choose openai, rebuild after embedding changes and recalibrate thresholds. Q4 classification also needs REALTIME_LLM_ENABLED=true. Default evaluation makes no hosted AI calls. Restart the backend after model/config changes.

## Known limitations and manual intervention

- Native-speaker listening, consented recordings in both markets and approved-source/compliance review remain required. Q3 Filipino/Taglish accuracy is limited on the small probe set; review uncertain text and confirm risky details.
- Callback/escalation records are mock requests. A human arranges actual contact; account verification, payment, renewal, fee waivers and final approval are outside this prototype.
- MMS is CC BY-NC 4.0; corpus audio has separate noncommercial/redistribution conditions. Commercial licenses/providers and regional legal review need owner intervention.
- A previously exposed provider key needs owner-side rotation if still valid. .env is ignored; .env.example has blank secrets.
- Regex PII handling is a baseline; scanned PDFs need OCR. Chunk/source metadata and rules require review. Near duplicates are flagged rather than reconciled.
- Q4 uses synthetic English recordings, final fixed chunks and offline role annotations. There is no real-call diarization, token streaming, crash resume or calibrated signal probability. One active replay is a CPU limit; capture/warmup are excluded from pipeline percentiles.
- The API has no authentication. Keep it on loopback; production needs access control, retention, encryption, provider/license review, proper migrations, ingestion coordination and load tests.
- No public deployment or external submission has been performed. Upload the required evaluator links through the owner's chosen channel after review.

## Production improvements

[Production plan](docs/production-improvements.md) covers ten-times-traffic design, sessions/connections, bounded workloads, quotas, fan-out, observability, noisy audio, reliability, audit, consent and privacy. These are proposed changes, not implemented infrastructure.
