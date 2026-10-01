# Q1 Phase 2 results

These are the original Phase 2 results, using Windows dictation for ASR. The current default is local Whisper `small.en`; see the [microphone fix and current verification](microphone-fix.md). The user subsequently confirmed a matching spoken-amount transcript on Chrome with a laptop microphone.

Generated from actual HTTP tool/controller replies and local speech providers. All data is synthetic.

The three WAV recordings render executed scripted-text conversations. They are synthesized dialogue, not human microphone calls. Separate WAV probes pass through the actual ASR endpoint.

| Recording | Scenarios | Observed result | Audio / transcript |
|---|---|---|---|
| cooperative | A | pass | [WAV](../data/audio/q1/cooperative.wav), [JSON](../evaluations/voice/cooperative.json) |
| objection_unknown_human | B, D, E | pass | [WAV](../data/audio/q1/objection_unknown_human.wav), [JSON](../evaluations/voice/objection_unknown_human.json) |
| conflict_callback | C, E | pass | [WAV](../data/audio/q1/conflict_callback.wav), [JSON](../evaluations/voice/conflict_callback.json) |

Expected scenarios: [A-E definitions](../evaluations/voice/scenarios.json). Each transcript includes expected checks, complete observed replies, sources, tool names, pass/fail and an audio timeline.

## Speech observations

| Synthetic input | Accepted | ASR confidence | Intended behavior reached |
|---|---|---|---|
| Yes. | True | 0.767 | True |
| Five hundred thousand. | False | 0.492 | False |
| Retail. | True | 0.780 | True |
| Forty eight months. | True | 0.622 | True |
| What is the processing fee? | True | 0.756 | True |
| I want a human representative. | True | 0.861 | True |

Actual accepted speech probes: 5/6. Intended behavior reached: 5/6. This small synthesized set is not an accuracy benchmark.

Confidence below 0.55 yields a repeat/type fallback without changing qualification. The probe JSON records real recognition output and measured HTTP request duration; these are not Q4 component-latency samples.

## Manual validation still required

- Open `/call`, allow microphone access, use a headset and exercise a live spoken FAQ and qualification flow.
- Check the recording-consent box, consent to qualification, complete/end a synthetic call and download its WAV. Public synthetic evidence does not replace human microphone testing.
- Windows English speech components must be installed. Cross-platform/native-language voice providers and Q4 streaming remain outside Phase 2.
- Lead, callback and escalation tools write mock local records. A human must coordinate a real callback; this app never contacts anyone.
- Hosted LLM interpretation is optional and tested with mocks only. No hosted calls were made for these results.
