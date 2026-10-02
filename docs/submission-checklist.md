# Final demo and submission checklist

Implementation/evidence for Phases 0–7 is present. Native-speaker/compliance and consented human-call validation remain external manual work. Every recording/report identifies synthesized inputs and the observed failures.

## Q1

- [x] Browser speech/text interface, backend tools and spoken replies: [Chrome regression](../evaluations/voice/browser-smoke.json).
- [x] Actual KB query and internal citations; cooperative, objection, incomplete/conflicting, unsupported fallback and human escalation: [Q1 report](q1-results.md).
- [x] Three synthesized scripted recordings with executed transcripts/results: report above.
- [x] Human laptop-microphone spoken amount confirmed by the user: [microphone fix](microphone-fix.md). This is a limited observation, not an accuracy benchmark.

## Q2

- [x] Six-format extraction, failed-source handling, cleaning, PII, dedupe, normalization and taxonomy: [KB specification](knowledge-base.md).
- [x] Schema, chunking, metadata, source/version/checksum tracking and manual chunk inspection: [chunk review](chunk-review.md).
- [x] Embeddings, atomic snapshot publication, metadata-filtered retrieval and citations connected to Q1.
- [x] Eleven actual retrieval cases: [report](q2-retrieval-evaluation.md). Ten correct; paperwork synonym safely misses.
- [x] Strict-mode `product`/`language` keyword indexes for remote Qdrant, existing-collection migration and staging-failure tests.

## Q3

- [x] Philippines English/Filipino/Taglish and Indonesia formal/colloquial/finance-mixed behavior: [Q3 report](q3-localization-report.md).
- [x] Three documented localization examples per market, current-register fallback and native MMS TTS compromises.
- [x] Two synthesized scripted recordings per market with executed HTTP replies.
- [x] Legitimate publisher-labeled Batak sample, actual ASR output/errors, configured language and provenance documented.
- [x] ASR probe errors retained: four of six intended speech behaviors reached; two short Filipino/Taglish failures.
- [ ] Native-speaker review and longer consented human recordings per market, including noisy finance/accent speech.
- [ ] Market-specific approved-source/compliance review; the project uses synthetic content.

## Q4

- [x] Original Q1 recording and synthetic Q1 stress recording replay incrementally at real-time speed.
- [x] Continuous final-chunk ASR, rolling transcript and live WebSocket/dashboard before playback ends.
- [x] Missed opportunity, compliance risk, frustration, payment difficulty and callback signals.
- [x] Noisy/ambiguous withholding, configurable confidence threshold, normalized dedupe, cooldown, priority and UI expiry.
- [x] Real acknowledged per-chunk samples and generated P50/P95 with sample count: [latency/quality report](q4-latency-report.md).
- [x] Per-window expected/emitted signals, FP/FN and suppression: [JSON](../evaluations/realtime/results.json).
- [x] Actual rendered Chrome demo video, success/fallback and live suppression: [video](../evaluations/realtime/live-demo.webm).
- [x] Ten-times-traffic and noisy-audio limits: [production improvements](production-improvements.md).
- [ ] Validate semantic classification on real reviewed calls; optional hosted classifier currently has mocked contract/failure/evidence tests.

## Submission hygiene

- [x] Evaluator-first README, architecture Mermaid, setup/test commands and blank-secret `.env.example`.
- [x] Public artifacts are synthetic; credentials/private recordings/model caches/corpus audio stay ignored.
- [x] Final automated tests and evidence files checked: [JUnit](../evaluations/final-tests.xml), [handoff](remaining-phases-verification.md).
- [x] Audio/transcript evidence and automated screen demo are available locally.
- [ ] Owner-side final native-language listening/compliance approval and any previously exposed-key rotation.
- [ ] Publish/upload the desired demo/submission links through the evaluator's required channel. No public deployment or external submission was requested.

Checked boxes refer to implementation and automated/local evidence. Unchecked items are deliberately disclosed rather than inferred from synthetic tests.
