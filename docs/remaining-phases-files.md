# Phases 4–7 files changed

The Phase 3 files already present at the start remain in the working tree; their full inventory is in [Phase 3 files](phase-3-files.md). This inventory covers the subsequent implementation and verification.

## Added backend

- `backend/app/api/realtime.py`: registered recordings/replay lifecycle, snapshots, bounded WebSocket events and acknowledgements.
- `backend/app/schemas/realtime.py`: strict replay/transcript/signal schemas.
- `backend/app/realtime/__init__.py`, `replay.py`, `transcription.py`, `signals.py`, `nudges.py`, `suppression.py`, `events.py`, `latency.py`, `service.py`: paced chunks, rolling context, evidence/role checks, guidance, suppression, persistence and measurement.
- `backend/app/providers/streaming_asr.py`, `stream_worker.py`: warm cancellable local fixed-chunk Whisper stream.
- `backend/tests/test_realtime.py`: actual clock pacing, role/negation rules, noisy/weak evidence, suppression, provider failure, redaction, acknowledgement, backpressure and disconnect tests.

## Updated backend/configuration

- `backend/app/main.py`, `backend/app/config.py`, `.env.example`: lifecycle wiring, bounds, cooldown/expiry, classification and acknowledgement options.
- `backend/app/providers/asr.py`, `backend/app/providers/llm.py`: streaming contract and optional exact-evidence structured semantic classifier.
- `backend/app/knowledge/index.py`, `backend/tests/test_index_failures.py`: remote strict-mode keyword index creation/migration, staging preservation on metadata-index failure.
- `backend/requirements.txt`, `backend/requirements-lock.txt`: pinned WebSocket support.

## Added/updated frontend

- `frontend/src/pages/LiveInsights.jsx`, `frontend/src/style.css`: recording controls, connection/replay status, active/expiring guidance, transcript, signals, latency and suppression.
- `frontend/src/components/TranscriptPanel.jsx`, `SignalList.jsx`, `NudgeCard.jsx`, `LatencyPanel.jsx`.
- `frontend/src/lib/websocket.js`: bounded reconnect attempts, snapshots and rendered acknowledgement.
- `frontend/tests/live-smoke.mjs`, `frontend/package.json`: actual streaming Chrome check, screenshots and demo video.

## Scripts, fixtures and evidence

- `scripts/create_realtime_fixtures.py`, `replay_audio.py`, `summarize_latency.py`, `evaluate_realtime.py`, `summarize_evidence.py`.
- `scripts/evaluate_localization.py`: current cross-reference to measured Q4 observations.
- `data/fixtures/replays.json`, `data/audio/q4/q1_insights.wav`.
- `evaluations/realtime/q1_insights-source.json`, `cli-insights.json`, `cli-cooperative.json`, `browser-smoke.json`, `results.json`, `latency.json`, `live-nudge.png`, `live-complete.png`, `live-demo.webm`.
- `evaluations/final-tests.xml`, `evaluations/final-summary.json`.
- Rerun evidence: `evaluations/retrieval/results.json`, `docs/q2-retrieval-evaluation.md`, `evaluations/voice/browser-smoke.json`, `evaluations/localization/browser-smoke.json`.

## Documentation

- Rewritten `README.md`: evaluator-first Q1–Q4, evidence table, complete setup/config/tests and limitations.
- Updated `docs/architecture.md`, `docs/q3-localization-report.md`.
- Added `docs/production-improvements.md`, `submission-checklist.md`, `evaluation-summary.md`, `q4-latency-report.md`, `remaining-phases-verification.md`, and this inventory.

No credentials, real customer audio, model downloads or regional corpus audio are public artifacts. Those paths stay ignored.
