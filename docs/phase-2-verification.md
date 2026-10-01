# Phase 2 verification

Scope: BUILD_STEPS Tasks 2.1-2.6 only, over the existing Phase 0-1 KB. AGENTS.md and BUILD_STEPS.md were read completely and left unchanged. No Phase 3 localization or Phase 4 streaming/nudges were implemented.

Verified on 2026-10-01 in the supplied Windows workspace.

| Check | Actual result |
|---|---|
| Backend tests | **98 passed**, exit 0. One upstream Starlette/httpx TestClient deprecation warning. [JUnit](../evaluations/phase-2-tests.xml). |
| Frontend build | `npm --prefix frontend run build`: exit 0, Vite 7.3.6. |
| Dependency consistency | `python -m pip check`: no broken requirements. npm dependency installation audited 68 packages with zero reported vulnerabilities. |
| Windows speech prerequisite | English-US desktop recognizer plus Microsoft David/Zira Desktop voices detected by `scripts/check_speech.ps1`. |
| HTTP conversation evidence | 3/3 scripted calls passed expected checks across scenarios A-E; actual response/state/tool/source evidence and synthesized WAVs in [Q1 results](q1-results.md). |
| ASR probes | 5/6 reached intended behavior through real speech endpoints. Amount probe confidence 0.492 was below 0.55 and left state unchanged. |
| Browser microphone path | Chrome used a synthetic 48-kHz WAV as its microphone source, captured PCM, called the actual ASR endpoint, retrieved the processing-fee source and rendered the answer. Observed confidence 0.755. |
| Browser call completion | Unknown FAQ fallback, redacted transcript, spoken output, mock escalation and consented WAV download passed. 3612716 recording bytes. No page errors. [Browser JSON](../evaluations/voice/browser-smoke.json). |
| Environment/secret check | `.env.example` parsed with blank key and local providers. A credential-pattern scan of non-ignored project text found zero values. `.env` and private recordings are ignored. |
| Relational compatibility | Tests preserve Phase 0 SQLite rows while adding call revisions; concurrent writes cannot silently overwrite; idempotent turns/actions and foreign keys verified. |

The tests deliberately exercise consent decline/withdrawal, pre-consent PII exclusion, incomplete/tentative/conflicting qualification, malformed values, unsupported FAQ, independent HTTP tools, stale/missing source evidence, changed rule thresholds, provider timeout/error/refusal, low-confidence ASR, invalid WAV, TTS failure, explicit voice confirmation and separate recording consent. Hosted interpretation request contracts use mocks only.

The first synthetic Chrome capture failed the confidence gate despite recognizing the sentence. Audio enhancement/AGC produced clipping; disabling enhancements in the push-to-talk path preserved the sample and the final browser test passed. The fixture is resampled to Chrome's 48-kHz fake-microphone format by the evidence script. No microphone constraints are altered by the final test harness.

## Reproduce

With Docker Qdrant, backend and frontend running and the synthetic KB ingested:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=evaluations/phase-2-tests.xml
npm --prefix frontend run build
powershell.exe -NoProfile -NonInteractive -File scripts/check_speech.ps1
.\.venv\Scripts\python.exe scripts/evaluate_voice.py
npm --prefix frontend run test:call
```

The evaluator creates fresh synthetic SQLite call/action rows on each run and overwrites only its fixed synthetic evidence files. It returns 1 if any scripted business-behavior check fails; ASR misses are recorded independently and honestly. `--without-audio` records absent speech evidence instead of claiming it works.

## Manual intervention / unresolved issues

- Allow microphone access and validate a human spoken call/recording with a headset. Automated evidence uses synthesized speech, not a human microphone or accent test. Record/review additional human test calls before asserting live quality.
- Install/configure the Windows English desktop recognizer and required voices if the speech check fails. Other operating systems need another ASR/TTS adapter; typed/KB behavior and isolated tests still work.
- Review synthetic policy/rule sources before replacing them with approved lender material. Update source IDs/version/checksum/quotes when necessary; source mismatches block preliminary eligibility.
- A key found in `.env.example` was moved to ignored `.env` and the template cleared. **Rotate the exposed key before hosted-provider use.** No hosted requests were made for this phase.
- Mock leads, callbacks and escalations require a human/real integration to act on them. Callback time is an unvalidated preference, not a confirmed appointment. Missing details remain missing.
- Browser recording is capped at five minutes and saved on explicit end/completion/escalation. Closing the page loses unsaved audio. Private raw audio requires a retention/access policy before real use.
- Q3 language switching, Q4 streaming/signal suppression/latency and broader assessment submission remain deferred. The existing Q2 semantic paperwork paraphrase miss remains documented.
