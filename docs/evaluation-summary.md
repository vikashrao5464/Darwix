# Unified evaluation summary

Generated from the stored JUnit and actual provider/replay reports.

| Area | Observed result | Evidence |
|---|---|---|
| Backend | 167 tests; 0 failures; 0 errors | [JUnit](../evaluations/final-tests.xml) |
| Q1 | Three scripted recorded calls; actual Chrome speech/tools regression | [Q1](q1-results.md), [Chrome](../evaluations/voice/browser-smoke.json) |
| Q2 | 11 queries; {'correct': 10, 'incorrect': 1} | [retrieval](q2-retrieval-evaluation.md) |
| Q3 | Scripted calls pass: True; 4/6 intended synthetic speech behaviors | [localization](q3-localization-report.md) |
| Q4 | 3 observed runs; passed: True; 34 acknowledged samples | [real-time report](q4-latency-report.md), [video](../evaluations/realtime/live-demo.webm) |

Synthetic evidence and mocked hosted contracts do not certify human accuracy, native naturalness, compliance or production scale. Known retrieval and Filipino/Taglish speech failures are retained.

Manual remaining: Native-speaker/compliance review; Consented human calls per market and broader accent/noise testing; Real contact coordination; Owner submission/publication and any exposed-key rotation. See [checklist](submission-checklist.md).
