# Phases 4–7 verification and handoff

Phases 4–7 implementation and local automated evidence are complete. The [submission checklist](submission-checklist.md) explicitly distinguishes synthetic evidence from the remaining native-speaker/compliance/human-call review. [Files changed](remaining-phases-files.md).

## Demonstrate

1. Open [the call page](http://127.0.0.1:5173/call). Start, consent, ask the processing fee, then an unsupported question. Use the laptop mic or type; confirm uncertain spoken values.
2. Open [the live page](http://127.0.0.1:5173/live), choose the Q1 stress recording and start replay. The server warms ASR, then streams six-second chunks at real-time speed. Watch opportunity, compliance, frustration and payment/callback nudges appear before audio ends.
3. Duplicate payment/callback windows and the weak opportunity/noise windows are withheld. Earlier nudges expire. Reconnect restores the persisted snapshot. The original cooperative Q1 recording is a negative control with no expected nudge.

[Recorded Chrome screen demo](../evaluations/realtime/live-demo.webm) includes the supported FAQ, unsupported fallback, live guidance and suppression. The screen video is silent; linked WAV call recordings provide audio. Speech is synthesized and unsafe-agent lines are explicitly injected test data.

## Checks and measured evidence

- Full backend suite passed; exact counts and JUnit are in [unified summary](evaluation-summary.md) and [XML](../evaluations/final-tests.xml). One upstream Starlette/httpx deprecation warning remains.
- Frontend production build and dependency consistency check passed.
- Actual Chrome Q1 microphone/TTS/tool/recording regression, Q3 multilingual speech/FAQ/fallback regression, and Q4 live/reconnect/expiry check passed. Browser microphone fixtures are synthetic and playback acceleration for Q1/Q3 UI automation is disclosed.
- Remote Qdrant strict-mode filtering was repaired by adding keyword indexes on product/language for existing and staged collections. The current configured index was rebuilt with 68 chunks; no credentials/environment values were changed. Actual retrieval returned the documented 10/11 result. The unsupported paperwork synonym safely misses; evaluator exit 1 is expected for that retained failure.
- Three real paced Q4 runs cover both CLI receipt and rendered Chrome acknowledgement, with actual ASR, per-window FP/FN, duplicate/weak suppression and generated component P50/P95/sample count. [Report](q4-latency-report.md), [JSON](../evaluations/realtime/results.json).
- Model warmup and up to six seconds of capture are excluded from pipeline percentiles. Delivery includes observer processing/return trip. Unacknowledged chunks are counted and omitted rather than assigned zero delivery time. Hosted semantic classification was mocked, not called live.

## Run commands (repository root)

For an existing environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
docker compose up -d qdrant
.\.venv\Scripts\python.exe scripts/ingest.py --rebuild
```

Fresh installations also need the ASR/native TTS setup scripts and Node dependencies in [README](../README.md). The public Q4 recording/catalogue are already present. To regenerate them, run `scripts/create_realtime_fixtures.py` with Windows David/Zira voices. The existing private regional sample can be recreated using `scripts/setup_accent_sample.py`.

Backend and frontend in separate terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
```

```powershell
npm --prefix frontend run dev
```

Checks (run replays sequentially):

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

`scripts/summarize_latency.py --call-id <id>` generates metrics from selected persisted samples. Replay registration prevents arbitrary filesystem reads; use a file listed in data/fixtures/replays.json. A fresh backend session requires a new replay ID; active replay recovery across restart is not implemented. Embedded Qdrant requires stopping the backend before CLI indexing.

## Assumptions, unresolved issues and manual intervention

- All business data is synthetic. Approved policy sources, source/rule review and market-specific compliance approval require a human.
- Native-speaker listening and consented human recordings in both markets remain required. Q3's two Filipino/Taglish probe errors and the limited regional sample are disclosed rather than hidden.
- The local stream emits final fixed chunks. Speaker annotations are synthetic fixture metadata, not diarization. Broader accent/noise/semantic evaluation is required before deployment. Confidence numbers are heuristic scores.
- One active replay, bounded queues and one-process WebSocket fan-out are prototype limits. Overload/provider failure stops safely. Authentication, distributed session recovery and production capacity remain design work in [production improvements](production-improvements.md).
- Allow microphone access and select the laptop mic for manual calls. If Chrome blocks replay audio, use the audio Play control; analysis continues. Restart services after configuration changes.
- Callbacks/escalations are mock requests. A human must arrange real contact. The app cannot verify or execute payment, renew policy coverage, waive fees or approve credit.
- Model/license and regional-corpus conditions assume noncommercial assessment use. Owner intervention is needed for commercial licensing, approved retention and regional privacy review. Private corpus/model/audio paths remain ignored.
- Any previously exposed provider key must be rotated by its owner if still valid. No hosted AI calls were used for default verification and no credentials were edited.
- External publication/submission and native-language signoff were not requested or inferred. The public demo artifacts are ready for owner review and upload through the required evaluator channel.
