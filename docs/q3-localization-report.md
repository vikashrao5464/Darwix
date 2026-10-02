# Q3 localization observations

Generated from actual HTTP replies and local ASR/TTS calls. Business facts and recorded call dialogue are synthetic. Native-speaker/compliance review remains required.

## Executed calls

| Call | Scripted checks | Audio | Transcript / results |
|---|---|---|---|
| ph_cooperative | pass | [WAV](../data/audio/q3/ph_cooperative.wav) | [JSON](../evaluations/localization/ph_cooperative.json) |
| ph_objection_callback | pass | [WAV](../data/audio/q3/ph_objection_callback.wav) | [JSON](../evaluations/localization/ph_objection_callback.json) |
| id_cooperative_formal | pass | [WAV](../data/audio/q3/id_cooperative_formal.wav) | [JSON](../evaluations/localization/id_cooperative_formal.json) |
| id_colloquial_mixed | pass | [WAV](../data/audio/q3/id_colloquial_mixed.wav) | [JSON](../evaluations/localization/id_colloquial_mixed.json) |

These four recordings synthesize scripted customer text and actual agent replies. They cover cooperative payment statements, objections, colloquial/mixed finance wording, same-language fallback, callbacks and escalation. They do not substitute for human call testing.

## ASR and TTS

ASR configuration: faster-whisper 1.2.1, medium multilingual, CPU int8. English uses `en`, Filipino uses `tl`, Taglish uses automatic language detection, and Indonesian uses `id`. Indonesian register is a conversation-state decision, not a separate ASR language. The previous `small.en` adapter remains in use for Q1. Domain vocabulary hints contain terms only, not business rules or expected transcripts.

TTS uses local Meta MMS `tgl` for Filipino/Taglish and `ind` for Indonesian. English uses Microsoft David Desktop. MMS is a single-language voice per market; English finance words in mixed speech use that voice, with pronunciation/prosody compromises. Formal/colloquial wording changes, but the voice does not acquire a regional accent. See the pinned revisions in `scripts/setup_localization.py`. MMS model licenses are CC BY-NC 4.0; this setup assumes noncommercial assessment use.

| Synthetic speech probe | Expected text | Observed text | Accepted / intended FAQ | WER | Request ms |
|---|---|---|---|---|---|
| ph_english (en) | What is a premium? | What is a premium? | True / True | 0.0 | 16171 |
| ph_filipino (fil) | Ano ang hulog? | No ang hulog. | True / False | 0.3333 | 15347 |
| ph_taglish (fil-en) | Ano po ang premium? | To po ang pinyo. | True / False | 0.5 | 24843 |
| id_formal (id-formal) | Apa tenor itu? | Apa tenor itu? | True / True | 0.0 | 13354 |
| id_colloquial (id-colloquial) | Apa cicilan itu, aku nggak ngerti? | Apa cicilan itu, aku nggak ngerti. | True / True | 0.0 | 13671 |
| id_mixed (id-en-mixed) | Apa down payment itu? | Apa down payment itu? | True / True | 0.0 | 13256 |

Intended speech behavior reached on 4/6 synthesized probes. This tiny set measures the transport/model/controller behavior, not human accuracy or naturalness. Detailed scores, citations and rejected/reviewed output are retained in [JSON](../evaluations/localization/results.json).

Uncertain or unavailable ASR leaves business state unchanged and returns review/type guidance in the current register. Missing evidence and unsupported benefits/fee waivers return a localized human-assistance offer. Missing TTS returns a localized read-the-screen message. Payment statements and spoken callback times require confirmation; no payment, coverage change or fee waiver is executed.

## ASR comparison

Previous configuration: faster-whisper 1.2.1, small multilingual, CPU int8. It reached intended behavior on 2/6 probes; its exact outputs and durations remain in the JSON under `previous_speech_observations`. The current configuration corrected the Indonesian mixed/colloquial transcriptions in this set but did not resolve the two short Filipino/Taglish probes. The controller also gained recognition of the standard Indonesian question word 'apakah', so intended-behavior changes cannot be attributed solely to the model. The two Filipino/Taglish errors returned localized fallbacks without a business-state update. The synthesized input itself may contribute pronunciation errors; native human testing is needed to separate TTS from ASR error.

The colloquial Indonesian baseline also lost a negation. High decoder scores did not guarantee correct words. Payment statements therefore require confirmation regardless of score. Finance-word errors such as premium/pinyo are retained rather than relabeled as successful recognition.

## Regional-accent observation

Tested publisher-labeled **Batak** Indonesian human speech from [INDspeech_NEWS_LVCSR](https://github.com/s-sakti/data_indsp_news_lvcsr) at revision `ecd9b8bb6d6567d1f486dd60c97497788781034c`. Source sample: `Ind001/Ind001_F_B_C_news_0000.wav`; local path: `data/state/accent/Ind001_F_B_C_news_0000.wav`. Duration: 2.66 seconds. This is original clean news speech, not a synthesized accent or finance call.

ASR: faster-whisper 1.2.1, medium multilingual, configured language `id`. Reference: `elza syarief mengaku`. Observed: `Elsa Syarif mengaku.`. Exact normalized words match: False. Fallback needed under the configured decoder threshold: False. Measured request: 12918 ms. Terminology errors: Not applicable: this news utterance has no required finance terms.

Attribution: Sakti et al. (2008), Development of Indonesian Large Vocabulary Continuous Speech Recognition System within A-STAR Project. The source is CC BY-NC-SA 4.0 and the publisher prohibits dataset copies in another public repository. Audio is downloaded to ignored `data/state/accent`; only provenance and observations are retained here. Reproduce with `scripts/setup_accent_sample.py`.

One short clean sample from one speaker; no accent robustness or noisy-finance-call claim. Native-speaker/compliance validation still required.

## Localization examples

The following are implemented draft copy choices, not claims of native-speaker approval.

| Market / English intent | Literal phrasing | Implemented phrasing | Reason |
|---|---|---|---|
| PH: Ask when a callback is convenient | Sa anong petsa at oras mo gustong tumanggap ng pabalik na tawag? | Anong araw at oras po kayo available for a callback? | Uses po and the familiar callback/available wording instead of a literal calque of callback. |
| PH: Acknowledge payment difficulty without promising changes | Nauunawaan ko ang iyong kahirapan sa pagbabayad. Nais mo ba ng pabalik na tawag? | Gets ko po, mahirap magbayad ngayon. Hindi ako makakapag-promise ng extension o coverage change. Gusto po ba ninyo ng callback? | Conversational acknowledgment and common insurance English terms preserve the speaker's mixed register; boundaries remain explicit. |
| PH: Explain that verified information is unavailable | Wala akong napatunayang impormasyon hinggil sa bagay na iyan. Nais mo bang kausapin ang isang kinatawan? | Wala po akong verified info tungkol diyan. Gusto po ba ninyong makausap ang isang representative? | Uses familiar contractions and finance-service English vocabulary with a polite Filipino question. |
| ID: Ask a convenient callback time | Pada hari dan jam apa Anda lebih memilih panggilan balik? | Enaknya ditelepon lagi hari apa, jam berapa? | Uses the colloquial enaknya and ditelepon lagi rather than the literal noun panggilan balik. |
| ID: Acknowledge payment difficulty | Saya mengerti bahwa Anda mengalami kesulitan pembayaran. Apakah Anda menginginkan panggilan kembali? | Paham, lagi susah bayar, ya. Aku nggak bisa janji hapus denda atau tambah waktu. Mau ditelepon lagi? | Short clauses and nggak follow the customer's casual register without implying a fee waiver. |
| ID: Explain unavailable information | Saya tidak memiliki informasi yang telah diverifikasi untuk pertanyaan tersebut. | Info itu belum verified. Mau berbicara dengan petugas? | Keeps the customer's finance-related English register while using Indonesian structure and a practical escalation question. |

## Manual validation and limits

- Have native speakers review Filipino/Taglish and both Indonesian registers, mixed-word pronunciation, politeness and finance language. Obtain approved business sources and regional compliance review before real use.
- Record human conversations per market with explicit consent; the four public WAVs here are synthesized scripted evidence. Expand accent tests to longer finance speech, different regions and noisy microphones.
- Language identification uses explicit selection plus a small deterministic vocabulary. Short acknowledgements preserve register; ambiguous language switches should use the UI selector. This is not broad multilingual intent understanding.
- Callback/escalation only create local mock records. A human must coordinate any actual contact. No payment is verified and no policy is renewed.
- CPU ASR/TTS workers have configured timeouts. These request durations are Q3 observations; Q4 streaming/component measurements are documented separately in the [Q4 report](q4-latency-report.md).

Reproduce: install speech dependencies, run `scripts/setup_localization.py`, `scripts/setup_accent_sample.py`, ingest the updated manifest, start the application and run `scripts/evaluate_localization.py`. `--without-audio` records text-only evidence and marks missing speech/accent evidence.
