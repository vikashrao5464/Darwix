# Q4 real-time observations and latency

Generated from real clock-paced recordings, local Whisper inference and observer acknowledgements.

## Executed replay runs

| Recording / observer | TP / FP / FN | Playback seconds | Transcript / nudge before end | Duplicate / weak withheld | Verdict |
|---|---|---|---|---|---|
| q1_insights / CLI receipt acknowledgement, not rendered UI | 5 / 0 / 0 | 66.001 / 66.0 | True / True | True / True | pass |
| q1_cooperative / CLI receipt acknowledgement, not rendered UI | 0 / 0 / 0 | 71.916 / 71.915 | True / False | False / False | pass |
| q1_insights / Chrome rendered UI acknowledgement (two animation frames) | 5 / 0 / 0 | 66.001 / 66.0 | True / True | True / True | pass |

Tiny synthesized English fixture set. Per-chunk signal FP/FN, not a human-call accuracy benchmark. Ground-truth text is not supplied to ASR/detector.

Full transcript/events and per-window errors: [JSON](../evaluations/realtime/results.json). The original Q1 cooperative call is a negative control; no nudge is expected. The Q1 stress call reuses its actual opening and adds explicitly synthetic risky-agent/objection phrases, noise and duplicate windows. Unsafe lines are deliberate evaluation injections, not assistant policy or ordinary controller output.

## Measured pipeline latency

Acknowledged sample count: **34**.

| Stage | P50 ms | P95 ms |
|---|---|---|
| asr_latency_ms | 2510.646 | 2777.689 |
| signal_latency_ms | 0.156 | 1.011 |
| llm_latency_ms | 0.004 | 0.146 |
| delivery_latency_ms | 6.242 | 31.975 |
| end_to_end_latency_ms | 2516.979 | 2787.296 |

Definitions: Server monotonic milliseconds from warmed replay start; model warmup excluded. Chunk capture adds up to REALTIME_CHUNK_SECONDS before audio_received_ms; reported pipeline latency excludes this capture interval.

Nudge stage complete to first observer acknowledgement; includes observer processing and return trip. llm_latency_ms is deterministic nudge construction time. Optional semantic classification belongs to signal time.

Client labels distinguish rendered Chrome acknowledgements from CLI receipt acknowledgements. Unacknowledged samples are omitted from percentiles and counted; no zero-delivery substitute is inserted. Persisted samples: [JSON](../evaluations/realtime/latency.json). These observations are not production service-level objectives.

## Implementation and limitations

- Six-second fixed chunks are read at real-time speed; only a WAV header and sidecar role/timing metadata are read upfront. Whisper remains warm for the replay, and final chunk transcripts are analyzed continuously. No reference words are given to recognition or detection.
- The local adapter emits final chunk text, not token-level partial transcripts. Word boundaries across chunks can lose context. No diarization: registered synthetic role annotations label single-role chunks; mixed-role or unannotated chunks remain unknown and do not produce role-dependent signals.
- Rolling context, bounded ASR queue, one active replay, bounded subscribers, provider timeouts and cancellation prevent unbounded accumulation. Overload/ASR failure stops analysis safely instead of claiming timely completion.
- Default signals use conservative rules and configured thresholds. The optional structured LLM classifier is opt-in, exact-evidence checked, timeout-protected and covered by mocked tests; no live hosted classifier was measured. Confidence scores are heuristics, not calibrated probabilities.
- Priority, cooldown, normalized evidence/action fingerprints and expiry suppress noise and duplicate nudges. Dashboard nudges expire; guidance performs no lead/payment/contract action. Weak or unclear recognition produces no signal.
- Expand evaluation to consented human calls, accents, noisy finance speech and real semantic-classifier runs before deployment. Six-second capture delay and measured inference time make this a chunked prototype.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts/create_realtime_fixtures.py
.\.venv\Scripts\python.exe scripts/replay_audio.py --file data/audio/q4/q1_insights.wav --output evaluations/realtime/cli-insights.json
.\.venv\Scripts\python.exe scripts/replay_audio.py --file data/audio/q1/cooperative.wav --output evaluations/realtime/cli-cooperative.json
npm --prefix frontend run test:live
.\.venv\Scripts\python.exe scripts/evaluate_realtime.py
.\.venv\Scripts\python.exe scripts/summarize_latency.py
```

Chrome demo: [video](../evaluations/realtime/live-demo.webm). The recording includes a supported Q1 FAQ, unsupported-question fallback, and Q4 live nudges/suppression. See [submission checklist](submission-checklist.md) for remaining human validation.
