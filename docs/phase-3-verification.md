# Phase 3 verification and handoff

Implemented Tasks 3.1-3.6 as a bounded prototype on the existing FastAPI/React application. Human/native-speaker and compliance validation remain manual requirements; the full assessment is not complete.

## Implemented behavior

- Philippines: English, Filipino/Tagalog and Taglish language/register state for life-insurance renewal reminders.
- Indonesia: formal, colloquial and finance-mixed Bahasa state for consumer-finance installment reminders.
- Sticky short acknowledgements, vocabulary-based switches and explicit response-language selection. Unsupported queries, ASR uncertainty/unavailability and TTS failure stay in the current register.
- Shared source-gated KB retrieval with product/language filters. Fourteen sources now yield 68 chunks, including 45 new synthetic localized chunks with source/version/section/record IDs.
- Deterministic consent and mock callback/escalation actions, redacted transcripts, idempotent turns and optimistic call revisions. Spoken callback times and all already-paid statements require confirmation. No payment verification, policy renewal or fee waiver is performed.
- Money/date readings are explicit synthetic source wording: PHP 1,500 and IDR 750,000 due October 15, 2026, spoken as words in each register. This is a fixed example, not a generic account/calendar integration.
- Local multilingual Whisper recognition and local Meta MMS Tagalog/Indonesian speech. Q1 retains its English recognizer and Windows voice.
- Two recorded synthesized scripted calls per market, six actual synthetic ASR probes, three implemented phrasing examples per market, and an original publisher-labeled Batak human speech observation.

## Checks

- Full backend test suite: **139 passed**, one upstream Starlette/httpx deprecation warning. [JUnit](../evaluations/phase-3-tests.xml).
- Frontend production build: passed.
- Dependency consistency and pinned-lock dry-run installation: passed.
- Q1 Chrome regression: microphone capture, actual ASR, cited FAQ, unavailable FAQ, speech, mock escalation and consented WAV passed. [JSON](../evaluations/voice/browser-smoke.json).
- Q3 Chrome regression: formal Indonesian microphone through actual multilingual ASR; cited reminder/FAQ, Taglish speech/FAQ and register-preserving fallbacks passed, with no page errors. [JSON](../evaluations/localization/browser-smoke.json). Synthetic microphone input and 8x speech playback were used for automation; this is not a human listening-quality assessment.
- Four scripted calls passed all expected HTTP/language/action checks. Actual speech probes, model comparisons, transcription errors and the Batak sample outcome are reported in [Q3 observations](q3-localization-report.md), with complete [JSON](../evaluations/localization/results.json).

## Reproduce from the repository root

Install the tested dependencies, prepare models, download the regional fixture privately and ingest:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
.\.venv\Scripts\python.exe scripts/setup_localization.py
.\.venv\Scripts\python.exe scripts/setup_accent_sample.py
docker compose up -d qdrant
.\.venv\Scripts\python.exe scripts/ingest.py --rebuild
```

Run the two processes in separate terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
```

```powershell
npm --prefix frontend run dev
```

Verify:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=evaluations/phase-3-tests.xml
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts/evaluate_localization.py
npm --prefix frontend run test:localization
npm --prefix frontend run test:call
```

The evaluator returns exit 1 for failed scripted checks and retains observed speech errors in its report. Speech probe acceptance, intended behavior and word errors are reported separately; an evaluator exit 0 does not mean all speech probes passed. `--speech-only` reuses the executed call evidence/WAVs and remeasures speech/accent after an ASR change. `--without-audio` explicitly marks absent speech evidence and is not an equivalent voice validation.

## Assumptions and manual intervention

- All account amounts, due dates and business definitions are synthetic demonstration sources; no official policies or customer accounts were supplied. Obtain approved sources and regional compliance review before real use.
- Refresh [the call page](http://127.0.0.1:5173/call), choose the market/scenario and register, grant microphone access and consent. Select the laptop microphone if the input meter stays empty. For a spoken language switch, send a typed reply with the selected response language first.
- Native speakers must review draft phrasing, politeness, Taglish/finance loanwords and TTS pronunciation/prosody. Public recordings are synthesized dialogues; separately record consented human calls for both markets. Errors observed on the tiny speech set are retained, and speech accuracy is not certified.
- The regional corpus permits noncommercial use with attribution but prohibits dataset copies in another public repository. Its audio remains ignored; `scripts/setup_accent_sample.py` reproduces the local download. One 2.66-second clean Batak sample does not demonstrate accent robustness. The sample contains no finance terminology, so finance-term error analysis needs another consented recording.
- MMS model licenses are CC BY-NC 4.0. This implementation assumes noncommercial assessment use; choose an appropriately licensed provider before commercial deployment. Setup downloads public pinned model revisions once; inference sends neither audio nor text to a hosted service. Windows David is still needed for English output.
- Callback/escalation records are mock requests. A human must arrange real contact. Confirm/correct uncertain transcriptions; the app cannot verify a payment or change a contract.
- New speech configuration is documented in `.env.example`. Defaults apply to existing environments that omit those variables; no credentials were edited. Restart the backend after model/config changes. Q4 streaming, live nudges and component-latency metrics remain deferred.
