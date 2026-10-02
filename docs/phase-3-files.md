# Phase 3 files changed

Only Phase 3 localization was added. Q4 remains deferred. The Phase 0-2 implementation and English recognition model are reused.

## Added implementation

- `backend/app/localization/__init__.py`
- `backend/app/localization/language_state.py`: market, language/register, sticky acknowledgements, explicit switches and ASR/TTS language mapping.
- `backend/app/localization/philippines.py`: Filipino/English/Taglish conversational copy and supported topic terms.
- `backend/app/localization/indonesia.py`: formal/colloquial/finance-mixed conversational copy and supported topic terms.
- `backend/app/localization/reminders.py`: consent, source-grounded reminder/definition handling, payment-statement confirmation, callbacks and escalation through shared tools.
- `backend/app/providers/mms_tts.py`, `backend/app/providers/mms_worker.py`: local native-language TTS with timeout/cancellation cleanup.
- `backend/tests/test_localization.py`: market/register, grounding, safe failure and mock-action tests.
- `scripts/setup_localization.py`: prepare pinned multilingual ASR and two native TTS models.
- `scripts/setup_accent_sample.py`: privately fetch one original publisher-labeled regional speech sample and matching reference/provenance.
- `scripts/evaluate_localization.py`: execute four scripted HTTP calls, synthesize their observed dialogue, probe actual ASR and generate the localization report.
- `frontend/tests/localization-smoke.mjs`: actual Chrome/native-speech/multilingual-ASR smoke test with synthetic microphone input.

## Added synthetic sources and evidence

- `data/raw/ph_reminder_en.json`, `data/raw/ph_reminder_fil.json`, `data/raw/ph_reminder_taglish.json`.
- `data/raw/id_reminder_formal.json`, `data/raw/id_reminder_colloquial.json`, `data/raw/id_reminder_mixed.json`.
- `data/audio/q3/ph_cooperative.wav`, `data/audio/q3/ph_objection_callback.wav`, `data/audio/q3/id_cooperative_formal.wav`, `data/audio/q3/id_colloquial_mixed.wav`: two synthesized scripted calls per market.
- `data/audio/q3/probe_ph_english.wav`, `data/audio/q3/probe_ph_filipino.wav`, `data/audio/q3/probe_ph_taglish.wav`, `data/audio/q3/probe_id_formal.wav`, `data/audio/q3/probe_id_colloquial.wav`, `data/audio/q3/probe_id_mixed.wav`.
- `evaluations/localization/scenarios.json`, `evaluations/localization/examples.json`.
- `evaluations/localization/ph_cooperative.json`, `evaluations/localization/ph_objection_callback.json`, `evaluations/localization/id_cooperative_formal.json`, `evaluations/localization/id_colloquial_mixed.json`.
- `evaluations/localization/results.json`, `evaluations/localization/browser-smoke.json`, `evaluations/phase-3-tests.xml`.
- `docs/q3-localization-report.md`, `docs/phase-3-verification.md`, `docs/phase-3-files.md`.

## Updated shared files

- `backend/app/config.py`, `backend/app/main.py`: provider configuration and shared controller/provider wiring.
- `backend/app/schemas/voice.py`: scenario selection, response language, language state and reminder status.
- `backend/app/voice/conversation.py`: dispatch localized scenarios through the existing voice lifecycle and transcript persistence.
- `backend/app/voice/tools.py`: prevent loan qualification/eligibility/lead actions on reminder calls.
- `backend/app/api/speech.py`: per-scenario ASR/TTS, native-language speech failures and unchanged-state review.
- `backend/app/providers/whisper_asr.py`, `backend/app/providers/whisper_worker.py`: explicit language hints on the existing cancellable worker.
- `backend/requirements.txt`, `backend/requirements-lock.txt`: pinned CPU PyTorch/Transformers and compatible dependencies.
- `data/raw/manifest.json`: six new product/language-filtered sources, 45 new chunks.
- `frontend/src/pages/CallDemo.jsx`, `frontend/src/lib/voice.js`, `frontend/package.json`: scenario/register selectors and speech request timeouts/check command.
- `.env.example`, `README.md`, `docs/architecture.md`: setup, limitations and reproducible commands.
- `evaluations/voice/browser-smoke.json`: rerun Q1 browser regression with the new shared UI.

Downloaded models, regional corpus audio, runtime state and private recordings live under already ignored paths. No new credentials or customer records are part of the implementation.
